"""Run the site: python app.py  (then open http://localhost:8000)"""
from grandma import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=8000)
