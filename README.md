# Course Explainer App

This is a simple web application built using Python and Flask that provides an overview and detailed information about various courses.

## Features

- Home page displaying a list of courses.
- Detailed course page with in-depth information.
- Responsive design with CSS styling.

## Project Structure

```
course-explainer-app
├── src
│   ├── app.py          # Entry point of the application
│   ├── views.py        # View functions for handling requests
│   ├── models.py       # Data models for managing course data
│   ├── templates       # HTML templates for rendering pages
│   │   ├── layout.html # Base layout for other templates
│   │   ├── index.html  # Homepage template
│   │   └── course.html # Course detail template
│   └── static          # Static files like CSS
│       └── css
│           └── styles.css # CSS styles for the application
├── tests               # Unit tests for the application
│   └── test_app.py     # Tests for view functions and routes
├── requirements.txt    # Project dependencies
├── .env                # Environment variables
└── README.md           # Project documentation
```

## Installation

1. Clone the repository:

   ```
   git clone <repository-url>
   cd course-explainer-app
   ```

2. Create a virtual environment:

   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   uv pip install -r requirements.txt
   ```

## Usage

To run the application, execute the following command:

```
python src/app.py
```

Visit `http://127.0.0.1:5000` in your web browser to view the application.

## Testing

To run the tests, use:

```
python -m unittest discover -s tests
```

## License

This project is licensed under the MIT License.
