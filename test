#!/bin/bash

#echo "Run test in developement environment."
#source ~/venv/bin/activate
#cd app
#python3 manage.py test
#flake8
#cd ..

echo "Run test in production docker development environment."
sudo docker compose run --rm app sh -c "python manage.py test"
sudo docker compose run --rm app sh -c "flake8"
