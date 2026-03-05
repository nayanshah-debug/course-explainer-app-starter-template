from flask import Flask, render_template
from views import index, course

app = Flask(__name__)

app.add_url_rule('/', endpoint='index', view_func=index)
app.add_url_rule('/course/<course_id>', endpoint='course', view_func=course)

if __name__ == '__main__':
    app.run(debug=True)