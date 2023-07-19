from typing import Callable, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


def schedule_task(task: Callable, schedules: List[str], timezone: str, task_args: dict):
    scheduler = AsyncIOScheduler()
    for schedule in schedules:
        hour, minute = map(int, schedule.split(':'))
        trigger = CronTrigger(hour=hour, minute=minute, timezone=timezone)
        scheduler.add_job(task, trigger=trigger, kwargs=task_args)
    scheduler.start()
