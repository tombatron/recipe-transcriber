/*
/**
 * Recipe Edit Form Handler
 * Manages dynamic ingredient/instruction fields, drag-and-drop reordering,
 * form dirty state tracking, and inline validation error clearing.
 */
window.recipeEdit = {
	isDirty: false,

	/**
	* Initialize the recipe edit form
	*/
    init() {
        const form = document.querySelector('[data-recipe-edit-form]');

        if (!form) {
            return;
        }

        this.setupDirtyTracking(form);
        this.setupDragAndDrop();
        this.setupIngredientDragAndDrop();
		this.setupValidationClearing(form);
		this.setupUnsavedWarning();
	},

	/**
	 * Track form changes to detect unsaved edits
	 */
	setupDirtyTracking(form) {
		const inputs = form.querySelectorAll('input, textarea, select');

		inputs.forEach((input) => {
			input.addEventListener('input', () => {
				this.isDirty = true;
			});
        });

		form.addEventListener('submit', () => {
			this.isDirty = false;
		});
    },

	/**
	 * Warn before navigating away with unsaved changes
	 */
	setupUnsavedWarning() {
		window.addEventListener('beforeunload', (event) => {
			if (this.isDirty) {
				event.preventDefault();
				event.returnValue = '';
			}
        });
		const cancelButton = document.querySelector('[data-cancel-button]');
		if (cancelButton) {
			cancelButton.addEventListener('click', (event) => {
				if (this.isDirty && !confirm('You have unsaved changes. Are you sure you want to cancel?')) {
					event.preventDefault();
				} else {
					this.isDirty = false;
				}
			});
        }
    },

	/**
	 * Clear validation errors when the user edits the field
	 */
	setupValidationClearing(form) {
		const validationInputs = form.querySelectorAll('[data-validation-target]');
		validationInputs.forEach((input) => {
			input.addEventListener('input', () => {
				input.classList.remove('border-red-300', 'bg-red-50');
				const errorMessage = input.parentElement.querySelector('[data-error-message]');
				if (errorMessage) {
					errorMessage.remove();
				}
            });
        });
    },

	/**
	 * Add a new ingredient row
	 */
	addIngredient() {
		const list = document.getElementById('ingredients-list');
		const template = document.getElementById('ingredient-template');

		if (!list || !template) {
			return;
		}

        const clone = template.content.cloneNode(true);
        const count = list.querySelectorAll('[data-ingredient-row]').length;

	    clone.querySelectorAll('input').forEach((input) => {
			const name = input.getAttribute('name');

			if (name) {
				input.setAttribute('name', name.replace('INDEX', count));
            }

		    const ingredientRow = clone.querySelector('[data-ingredient-row]');

            if (ingredientRow) {
                ingredientRow.setAttribute('draggable', 'true');
            }

		    list.appendChild(clone);
		    this.isDirty = true;
        });
	},

	/**
	 * Remove an ingredient row
	 */
	removeIngredient(button) {
		const row = button.closest('[data-ingredient-row]');
		const list = document.getElementById('ingredients-list');
		if (!row || !list) {
			return;
		}

		if (list.querySelectorAll('[data-ingredient-row]').length <= 1) {
			return;
		}

		row.remove();
		this.reindexIngredients();
		this.isDirty = true;
	},

	/**
	 * Reindex ingredient names after reorder
	 */
	reindexIngredients() {
		const rows = document.querySelectorAll('[data-ingredient-row]');
		rows.forEach((row, index) => {
			row.querySelectorAll('input').forEach((input) => {
				const name = input.getAttribute('name');
				if (name) {
					input.setAttribute('name', name.replace(/\[\d+\]/, `[${index}]`));
				}
			});
        });
    },

	/**
	 * Add a new instruction row
	 */
	addInstruction() {
		const list = document.getElementById('instructions-list');
		const template = document.getElementById('instruction-template');

		if (!list || !template) {
			return;
		}

        const clone = template.content.cloneNode(true);
        const count = list.querySelectorAll('[data-instruction-row]').length;
        const textarea = clone.querySelector('textarea');

        if (textarea) {
            const name = textarea.getAttribute('name');
            if (name) {
                textarea.setAttribute('name', name.replace('INDEX', count));
            }
        }

        const stepNumberBadge = clone.querySelector('.bg-amber-600');

        if (stepNumberBadge) {
            stepNumberBadge.textContent = count + 1;
        }
        const instructionRow = clone.querySelector('[data-instruction-row]');
        if (instructionRow) {
            instructionRow.setAttribute('draggable', 'true');
        }
        list.appendChild(clone);
        this.isDirty = true;
	},

	/**
	 * Remove an instruction row
	 */
	removeInstruction(button) {
		const row = button.closest('[data-instruction-row]');
		const list = document.getElementById('instructions-list');
		if (!row || !list) {
			return;
		}

		if (list.querySelectorAll('[data-instruction-row]').length <= 1) {
			return;
		}

		row.remove();
		this.reindexInstructions();
		this.isDirty = true;
	},
    
	/**
	 * Reindex instruction step numbers and field names
	 */
	reindexInstructions() {
		const rows = document.querySelectorAll('[data-instruction-row]');
		rows.forEach((row, index) => {
			const stepBadge = row.querySelector('.bg-amber-600');
			if (stepBadge) {
				stepBadge.textContent = index + 1;
            }
			const textarea = row.querySelector('textarea');
			if (textarea) {
				const name = textarea.getAttribute('name');
				if (name) {
					textarea.setAttribute('name', name.replace(/\[\d+\]/, `[${index}]`));
				}
			}
        });
    },

	/**
	 * Generic reorder helper for drag-and-drop
	 */
	setupReorder(listId, rowSelector, reindexFn) {
		const list = document.getElementById(listId);
		if (!list) {
			return;
		}

		if (list.dataset.reorderBound === 'true') {
			return;
		}

		list.dataset.reorderBound = 'true';

		let dragged = null;
	    let dropTarget = null;

	    const resetHighlight = () => {
			list.querySelectorAll(rowSelector).forEach((row) => row.classList.remove('border-amber-600', 'bg-amber-50', 'border-2'));
		};

		list.addEventListener('dragstart', (event) => {
			const row = event.target.closest(rowSelector);

			if (!row) {
				return;
            }

	        dragged = row;

	        row.classList.add('opacity-50');

	        event.dataTransfer.effectAllowed = 'move';
            event.dataTransfer.setData('text/plain', '');
        });

        list.addEventListener('dragend', () => {
            if (dragged) {
                dragged.classList.remove('opacity-50');
            }

            resetHighlight();

            dragged = null;
            dropTarget = null;
        });

        list.addEventListener('dragover', (event) => {
            if (!dragged) {
                return;
            }

            event.preventDefault();
            event.dataTransfer.dropEffect = 'move';
            const row = event.target.closest(rowSelector);

            if (!row || row === dragged) {
                return;
            }

            if (dropTarget && dropTarget !== row) {
                dropTarget.classList.remove('border-amber-600', 'bg-amber-50', 'border-2');
            }

            dropTarget = row;
            row.classList.add('border-amber-600', 'bg-amber-50', 'border-2');
        });

        list.addEventListener('drop', (event) => {
            if (!dragged || !dropTarget) {
                return;
            }

            event.preventDefault();
            dropTarget.classList.remove('border-amber-600', 'bg-amber-50', 'border-2');

            const rows = Array.from(list.querySelectorAll(rowSelector));
            const fromIndex = rows.indexOf(dragged);
            const toIndex = rows.indexOf(dropTarget);

            if (fromIndex < toIndex) {
                dropTarget.after(dragged);
            } else {
                dropTarget.before(dragged);
            }

            if (typeof reindexFn === 'function') {
                reindexFn();
            }

            this.isDirty = true;
        });
	},

	setupDragAndDrop() {
		this.setupReorder('instructions-list', '[data-instruction-row]', () => {
			this.reindexInstructions();
		});
	},

	setupIngredientDragAndDrop() {
		this.setupReorder('ingredients-list', '[data-ingredient-row]', () => {
			this.reindexIngredients();
		});
	},
};

// Initialize when Turbo loads the page/frame
document.addEventListener('turbo:load', () => {
	recipeEdit.init();
});

// Also initialize when a Turbo frame loads
document.addEventListener('turbo:frame-load', () => {
	recipeEdit.init();
});

// Fallback for traditional page loads
if (document.readyState === 'loading') {
	document.addEventListener('DOMContentLoaded', () => {
		recipeEdit.init();
	});
} else {
	recipeEdit.init();
}