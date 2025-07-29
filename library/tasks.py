from datetime import datetime

from celery import shared_task
from .models import Loan
from django.core.mail import send_mail
from django.conf import settings

@shared_task
def send_loan_notification(loan_id):
    try:
        loan = Loan.objects.get(id=loan_id)
        member_email = loan.member.user.email
        book_title = loan.book.title
        send_mail(
            subject='Book Loaned Successfully',
            message=f'Hello {loan.member.user.username},\n\nYou have successfully loaned "{book_title}".\nPlease return it by the due date.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member_email],
            fail_silently=False,
        )
    except Loan.DoesNotExist:
        pass


@shared_task
def check_overdue_loans():
    loans = Loan.objects.filter(is_returned=False, due_date__lt=datetime.today()).select_related('book', 'member')

    for loan in loans:
        user = loan.member.user
        book_name = loan.book.title

        send_mail(
            f"Over Due Notification: {book_name}",
            f"Dear {user.username}, \n\nYour {book_name} is Over due.\n\nPlease return the book as soon as possible",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )

