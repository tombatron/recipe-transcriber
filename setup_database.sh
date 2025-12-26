#!/bin/bash

echo "Recipe Transcriber - Database Setup"
echo "===================================="
echo ""

# Set Flask app
export FLASK_APP=src.receipe_transcriber

# Check if migrations folder exists
if [ ! -d "migrations" ]; then
    echo "📦 Initializing Flask-Migrate..."
    flask db init
    echo ""
fi

# Create migration
echo "📝 Creating database migration..."
flask db migrate -m "Initial migration"
echo ""

# Apply migration
echo "✅ Applying database migration..."
flask db upgrade
echo ""

# Alternative: Simple database creation (without migrations)
echo "🔧 Alternative: Creating tables directly..."
flask init-db
echo ""

echo "✅ Database setup complete!"
echo ""
echo "You can now run the application with:"
echo "  ./run_dev.sh"
echo ""
