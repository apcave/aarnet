# Aarnet
Backend Network Software Engineering Assessment

## Network Topology Tracing



#### Current Package Features
* SQLite, db local file for persistent storage.
* Not stateless will not work in docker container.

Django uses the Model-View-Template (MVT) pattern, where models define data, views handle request logic, and templates or serialized responses present the output.

The project follows a Test-Driven Development (TDD) workflow, with unit and API tests written first to validate behaviour before final implementation changes.

Server-side login and security controls are enforced in the Django application, ensuring authentication and authorization checks occur on the backend rather than relying on client-side only protections.

Runtime tests exercise the application under realistic traffic and load conditions to validate behaviour outside the basic unit-test suite.

The data model uses cascading deletes for dependent records so removing a parent object also cleans up related resources, while validation rules enforce topological integrity such as requiring an interface to be attached to an existing device and preventing invalid cross-device or duplicate relationships.

An additional Network abstraction was introduced to provide a higher-level grouping layer above Site records, reflecting the real-world hierarchy of network, site, device, interface, and connection within the application domain.

Connection status is derived from the relationship state rather than being freely editable by the client, and the system enforces data restrictions to maintain valid network topology and prevent inconsistent records.

## Project Scripts
The project root includes a small set of shell helper scripts to manage the local Django environment, setup, linting, and test runs.

- `setup` - Creates the local Python virtual environment, installs project dependencies from `requirements.txt`, copies the sample environment file into `.env`, recreates the local database, and runs Django checks, migrations, the superuser bootstrap, and static collection.
- `run` - Activates the virtual environment, loads `.env`, and starts the Django development server on `0.0.0.0:8000` with flake8 run first for a quick quality check.
- `delete_db` - Removes the SQLite database and any generated migration files so the app can be rebuilt from a clean state, then runs Django system checks and migrations again.
- `test-dev` - Activates the virtual environment, loads the env config, and runs the Django test suite for the project in the local development environment.
- `test-runtime` - Runs a lightweight runtime validation flow by clearing the database, then executes the stochastic load script with a single worker and a low error rate to exercise the API under realistic load.
- `lint` - Runs `autopep8` recursively on the app and runtime-test folders with a 79-character line limit, then executes `flake8` to enforce the same style rule.

## Setup and Test
To setup the DJANGO environment locally.
On mac OS run:
```bash
./setup
./run
open "http://localhost:8000/api/docs"
```

The project serves a Swagger API interface at http://localhost:8000/api/docs/ once the server is running.

The Django admin portal is available at http://localhost:8000/admin and can be accessed with the credentials in the project `.env` file:
- Email: `admin@example.com`
- Username: `Admin User`
- Password: `adminpass123`

## Useful Commands
```bash
./test-dev
./lint
./delete_db
./test-runtime
```


