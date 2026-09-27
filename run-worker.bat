@echo off
cd /d D:\Ansh\Study\Sem_7\Internship\seo\backend

echo Starting Celery Worker...

.\.venv\Scripts\celery.exe -A app.celery_app.celery_app worker --loglevel=INFO --pool=solo

pause