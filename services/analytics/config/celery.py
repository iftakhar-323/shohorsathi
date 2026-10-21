from shohor_common.celery import make_celery

app = make_celery("analytics")
