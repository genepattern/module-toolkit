# GenePattern Module Generator Web UI

A minimal Django web application that provides a frontend for the `generate-module.py` script.

## Features

- Simple username/password authentication (configured via `.env`)
- Web form to run the module generation script
- View and download generated module files
- Track user run counts with configurable limits
- Resume previous runs

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure the `.env` file:
   - `SECRET_KEY`: Django secret key (change in production!)
   - `DEBUG`: Set to `False` in production
   - `USERS`: Comma-separated list of usernames
   - `PASSWORDS`: Comma-separated list of passwords (matching order with USERS)
   - `MAX_RUNS_PER_USER`: Maximum runs allowed per user (default: 20)
   - `MODULE_TOOLKIT_PATH`: Path to the module-toolkit directory

3. Run the development server:
   ```bash
   python manage.py runserver
   ```

4. Access the application at `http://localhost:8000`

## User Run Tracking

User runs are tracked in `generated-modules/{username}/user_stats.json`. Admins can edit this file to:
- View run history
- Override max runs for specific users by adding `"max_runs": <number>`

## File Structure

```
webapp/
├── .env                 # Environment configuration
├── README.md            # This file
├── requirements.txt     # Python dependencies
├── manage.py            # Django management script
├── config/              # Django project settings
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── generator/           # Main application
    ├── __init__.py
    ├── views.py
    ├── urls.py
    └── templates/
        └── generator/
            ├── login.html
            └── dashboard.html
```

## Notes

- No database is used; all data is read from the filesystem
- Bootstrap 5.2 is loaded from CDN
- Generated modules are stored in `{MODULE_TOOLKIT_PATH}/generated-modules/{username}/`

