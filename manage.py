#!/usr/bin/env python
"""
================================================================
  manage.py — Django Management Utility
  Run: python manage.py runserver
================================================================
"""
import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_disease.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Couldn't import Django.") from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
