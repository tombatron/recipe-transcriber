import json
import re
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field, ValidationError
from ollama import chat, ResponseError
from flask import current_app
import logging

logger = logging.getLogger(__name__)


class IngredientSchema(BaseModel):
    """Schema for individual ingredient in recipe."""
    quantity: Optional[str] = Field(default=None, description="Amount of ingredient (e.g., '2', '1.5')")
    unit: Optional[str] = Field(default=None, description="Unit of measurement (e.g., 'cups', 'tbsp')")
    item: str = Field(..., description="Name of the ingredient")


class RecipeSchema(BaseModel):
    """Schema for structured recipe output from Ollama."""
    title: str = Field(..., description="Name of the recipe")
    ingredients: List[IngredientSchema] = Field(default_factory=list, description="List of ingredients")
    instructions: List[str] = Field(default_factory=list, description="Step-by-step cooking instructions")
    prep_time: Optional[str] = Field(default=None, description="Preparation time (e.g., '15 minutes')")
    cook_time: Optional[str] = Field(default=None, description="Cooking time (e.g., '30 minutes')")
    servings: Optional[str] = Field(default=None, description="Number of servings (e.g., '4', 'serves 6')")
    notes: Optional[str] = Field(default=None, description="Additional notes, tips, or variations")


class OllamaService:
    """Service for transcribing recipes from images using Ollama vision models.
    
    Uses a two-pass approach for maximum accuracy with handwritten recipes:
    1. First pass: Extract all visible text from the image
    2. Second pass: Structure extracted text into recipe format with schema validation
    """
    
    def __init__(self):
        self.model = None
    
    def _get_config(self):
        """Load configuration from Flask app context."""
        if not self.model:
            self.model = current_app.config.get('OLLAMA_MODEL', 'qwen3-vl')
            self.structure_model = current_app.config.get('STRUCTURE_MODEL') or self.model
            logger.info(f"[CONFIG] Vision model: {self.model} | Structure model: {self.structure_model}")
    
    def transcribe_recipe(self, image_path: str) -> dict:
        """
        Transcribe a recipe from an image using Ollama vision model.
        
        Uses a two-pass approach for maximum accuracy:
        1. First pass: Extract all raw text from the image
        2. Second pass: Structure the text into validated recipe format
        
        Args:
            image_path: Path to the recipe image file
            
        Returns:
            Dictionary with keys: title, ingredients, instructions, prep_time, cook_time, servings, notes
            
        Raises:
            Exception: If Ollama service fails or model not found
        """
        self._get_config()
        
        try:
            # Verify image file exists
            image_file = Path(image_path)
            if not image_file.exists():
                raise FileNotFoundError(f"Image file not found: {image_path}")
            
            # FIRST PASS: Extract all visible text with high accuracy
            extraction_prompt = """You are an expert at reading and transcribing text from images, including handwritten and printed text.

Your task: CAREFULLY read ALL visible text in this image. Pay special attention to:
- Handwritten text (read slowly, consider context if unclear)
- Handwritten text in cursive script (read multiple times if unclear, use context to aid interpretation)
- Printed text (both typed and handwritten)
- Numbers, measurements, and abbreviations
- Any notes, tips, marginalia, or special instructions

IMPORTANT: Be thorough and precise. Read every word carefully multiple times if needed.

Extract EVERY piece of visible text exactly as you see it. Return only the complete text transcription, nothing else."""

            logger.info(f"\n{'='*70}")
            logger.info(f"[PASS 1] TEXT EXTRACTION from {Path(image_path).name}")
            logger.info(f"Vision model: {self.model}")
            logger.info(f"Calling Ollama...")
            
            response1 = chat(
                model=self.model,
                messages=[{
                    'role': 'user',
                    'content': extraction_prompt,
                    'images': [str(image_file)]
                }],
                stream=False,
                options={
                    'temperature': 0,          # Deterministic output
                    'top_p': 0.95,             # Reduce hallucination
                    'top_k': 40,               # Limit token selection
                    'repeat_penalty': 1.1,    # Prevent repetition
                    'num_predict': 4096,      # Increase for complex recipes
                    'num_ctx': 8192,          # Larger context window
                }
            )
            
            extracted_text = response1.message.content
            if not extracted_text and hasattr(response1.message, 'thinking') and response1.message.thinking:
                logger.info("[PASS 1] Using thinking field from model response")
                extracted_text = response1.message.thinking
            
            logger.info(f"[PASS 1] ✓ Extracted {len(extracted_text) if extracted_text else 0} characters")
            if extracted_text:
                logger.info(f"[PASS 1] Preview: {extracted_text[:150]}...")
                logger.info("[PASS 1] Full extraction follows:\n%s", extracted_text)
            
            if not extracted_text or not extracted_text.strip():
                logger.error("❌ Empty text extracted from image in first pass")
                logger.error(f"Full response object: {response1}")
                raise Exception("Failed to extract text from image - empty response from Ollama")
            
            # SECOND PASS: Structure the extracted text into recipe format (strict JSON)
            logger.info(f"\n{'='*70}")
            logger.info(f"[PASS 2] RECIPE STRUCTURING to JSON")
            logger.info(f"Structure model: {self.structure_model}")
            logger.info(f"Extracted text: {len(extracted_text)} chars")
            logger.info(f"Calling Ollama for JSON conversion...")
            
            result = self._structure_text_to_recipe(extracted_text)
            
            logger.info(f"\n{'='*70}")
            logger.info(f"✓✓✓ SUCCESS ✓✓✓")
            logger.info(f"Title: {result['title']}")
            logger.info(f"Ingredients: {len(result['ingredients'])} items | Instructions: {len(result['instructions'])} steps")
            if result.get('prep_time'):
                logger.info(f"Prep time: {result['prep_time']}")
            if result.get('cook_time'):
                logger.info(f"Cook time: {result['cook_time']}")
            if result.get('servings'):
                logger.info(f"Servings: {result['servings']}")
            logger.info(f"{'='*70}\n")
            return result
                
        except ResponseError as e:
            error_msg = str(e)
            if "not found" in error_msg.lower():
                logger.error(f"❌ Ollama model '{self.model}' not found. Please pull it first with: ollama pull {self.model}")
                raise Exception(f"Ollama model '{self.model}' not found. Pull it with: ollama pull {self.model}")
            elif "connection" in error_msg.lower():
                logger.error("❌ Cannot connect to Ollama service. Is it running?")
                raise Exception("Cannot connect to Ollama service. Is it running on localhost:11434?")
            else:
                logger.error(f"❌ Ollama service error: {error_msg}")
                raise Exception(f"Ollama service error: {error_msg}")
                
        except FileNotFoundError as e:
            logger.error(f"❌ File error: {e}")
            raise

        except Exception as e:
            logger.error(f"❌ Unexpected error in transcribe_recipe: {e}")
            raise

    def _structure_text_to_recipe(self, extracted_text: str) -> dict:
        """Structure extracted text into a recipe using strict schema and retries."""
        # Direct instructions for structuring
        system_msg = "You convert recipe text into JSON. Reply with ONLY a single JSON object. No prose, no markdown."

        user_msg = (
            "Convert the following recipe text into JSON with these fields: "
            "title (string), ingredients (array of {quantity, unit, item}), instructions (array of strings), "
            "prep_time (string|null), cook_time (string|null), servings (string|null), notes (string|null). "
            "Use null for missing fields. Do not add fields. Return ONLY the JSON object.\n\n"
            "Text:\n" + extracted_text
        )


        messages = [
            {'role': 'system', 'content': system_msg},
            {'role': 'user', 'content': user_msg},
        ]

        options = {
            'temperature': 0,
            'top_p': 0.95,
            'top_k': 40,
            'repeat_penalty': 1.1,
            'num_predict': 2048,
        }

        schema_format = RecipeSchema.model_json_schema()
        use_format_param = 'vision' not in (self.structure_model or '')

        # Try up to 2 corrective retries if the model emits prose or invalid JSON
        last_response_text = ''
        for attempt in range(3):  # initial + 2 retries
            try:
                if attempt == 0:
                    logger.info(f"  [Attempt 1/3] Sending structuring request with schema format...")
                else:
                    logger.info(f"  [Attempt {attempt+1}/3] Retry with corrective message...")
                
                response = chat(
                    model=self.structure_model,
                    messages=messages,
                    stream=False,
                    format=schema_format if use_format_param else None,
                    options=options,
                )
                
                # Try to get content from various fields
                response_text = response.message.content
                
                # If content is empty, check thinking field
                if not response_text and hasattr(response.message, 'thinking') and response.message.thinking:
                    logger.info(f"    [DEBUG] Content empty, using thinking field")
                    response_text = response.message.thinking
                
                # Log full response structure for debugging if empty
                if not response_text:
                    logger.warning(f"    [DEBUG] Empty response. Message fields: {dir(response.message)}")
                    logger.warning(f"    [DEBUG] Message dict: {response.message.__dict__}")
                
                last_response_text = response_text
                logger.info(f"    ✓ Response received: {len(response_text)} chars")
                
                recipe_json = json.loads(response_text)
                logger.info(f"    ✓ Valid JSON parsed")
                
                recipe_data = RecipeSchema(**recipe_json)
                logger.info(f"    ✓ Schema validation passed")
                logger.info(f"  ✓✓ SUCCESS on attempt {attempt + 1}: '{recipe_data.title}'")
                return recipe_data.model_dump()
            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"    ❌ Attempt {attempt + 1} failed: {type(e).__name__}")
                logger.warning(f"       Response text (first 200 chars): '{response_text[:200] if response_text else '[EMPTY]'}'")
                if isinstance(e, json.JSONDecodeError):
                    logger.debug(f"       JSON error: {e.msg} at position {e.pos}")
                else:
                    logger.debug(f"       Validation: {str(e)[:150]}")
                # Prepare corrective follow-up message and retry
                corrective = (
                    "Your last answer was not a single JSON object matching the schema. "
                    "Reply with ONLY the JSON object. No prose, no markdown, no code fences. "
                    "Use null for missing fields."
                )
                messages = [
                    {'role': 'system', 'content': system_msg},
                    {'role': 'user', 'content': user_msg},
                    {'role': 'user', 'content': corrective},
                ]
                continue

        # Final fallback: try to extract JSON block from the last response
        logger.warning(f"  All 3 attempts failed. Trying defensive JSON extraction...")
        extracted = self._extract_json_from_text(last_response_text)
        if extracted is not None:
            logger.info(f"    ✓ Found JSON block in response")
            try:
                recipe_data = RecipeSchema(**extracted)
                logger.info(f"  ✓✓ Defensive extraction succeeded: '{recipe_data.title}'")
                return recipe_data.model_dump()
            except ValidationError as e:
                logger.error(f"    ❌ Extracted JSON failed validation: {e}")
        # If all else fails, raise
        logger.error(f"\n❌❌❌ FAILED: Could not obtain schema-compliant JSON")
        logger.error(f"Last response: {last_response_text[:300]}...")
        raise Exception("Failed to obtain schema-compliant JSON from structuring pass")

    def _extract_json_from_text(self, text: str) -> Optional[dict]:
        """Extract first valid JSON object from text, handling various formats."""
        if not text:
            return None
        
        # Try fenced ```json blocks first
        fence = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
        if fence:
            try:
                return json.loads(fence.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find valid JSON by looking for { and finding matching }
        # Start from each { and expand outward until valid JSON is found
        brace_starts = [m.start() for m in re.finditer(r'\{', text)]
        for start_pos in brace_starts:
            # Try increasingly longer substrings
            for end_pos in range(len(text), start_pos, -1):
                candidate = text[start_pos:end_pos]
                try:
                    result = json.loads(candidate)
                    logger.debug(f"Successfully extracted JSON from position {start_pos}:{end_pos}")
                    return result
                except json.JSONDecodeError:
                    continue
        
        return None

    def check_connection(self) -> bool:
        """Check if Ollama service is available and required model is installed.
        
        Returns:
            True if service and model are available, False otherwise
        """
        self._get_config()
        try:
            logger.info(f"Testing Ollama connection...")
            logger.info(f"  Vision model: {self.model}")
            logger.info(f"  Structure model: {self.structure_model}")
            response = chat(
                model=self.model,
                messages=[{
                    'role': 'user',
                    'content': 'Hello'
                }],
                stream=False,
                options={'num_predict': 1}
            )
            logger.info(f"✓ Ollama service online")
            logger.info(f"✓ Vision model '{self.model}' ready")
            if self.structure_model != self.model:
                logger.info(f"✓ Structure model '{self.structure_model}' available")
            return True
            
        except ResponseError as e:
            if "not found" in str(e).lower():
                logger.error(f"❌ Model '{self.model}' not found on system")
                logger.error(f"   Fix: ollama pull {self.model}")
            else:
                logger.error(f"❌ Ollama service error: {e}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Cannot reach Ollama (localhost:11434): {e}")
            return False


ollama_service = OllamaService()
