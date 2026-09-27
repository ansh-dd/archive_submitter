@echo off

echo Starting PRJ-09 Advanced Architecture...

start "PRJ09 FastAPI" cmd /k "cd /d D:\Ansh\Study\Sem_7\Internship\seo\backend && .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"

timeout /t 2 >nul

start "PRJ09 Celery Worker" cmd /k "cd /d D:\Ansh\Study\Sem_7\Internship\seo\backend && .\.venv\Scripts\celery.exe -A app.celery_app.celery_app worker --loglevel=INFO --pool=solo"

timeout /t 2 >nul

start "PRJ09 Celery Beat" cmd /k "cd /d D:\Ansh\Study\Sem_7\Internship\seo\backend && .\.venv\Scripts\celery.exe -A app.celery_app.celery_app beat --loglevel=INFO"

echo.
echo FastAPI, Celery Worker and Celery Beat started.
echo.
pause