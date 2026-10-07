# notify

Sends overdue-invoice reminders through the SMS provider. Rate-limited sends (provider HTTP 429) are retried by the next scheduler pass; other errors are permanent.
