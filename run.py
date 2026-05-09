import os
from app import create_app, db
from app.models import *  # noqa: registers all models with SQLAlchemy

app = create_app(os.getenv('FLASK_ENV', 'development'))


@app.shell_context_processor
def make_shell_context():
    return dict(db=db, app=app)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Creates tables if they don't exist
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=app.config['DEBUG'])
