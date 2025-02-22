#!/bin/bash
#
# PyTesira development checks
# TODO: there's probably a better way of doing this, maybe also put in Git commit hooks?
#
printf "\nSyntax error/undefined names checks\n"
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

printf "\nCode style checks\n"
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=128 --statistics

printf "\nUnit tests\n"
pytest