from celery import Celery

app = Celery(
    "worker",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0",
)


@app.task
def ping():
    """Simple placeholder task to confirm the worker is set up and can
    execute a task end-to-end. Real inference-triggering tasks to be added."""
    return "pong"