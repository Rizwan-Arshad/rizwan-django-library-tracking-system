from datetime import timedelta

from django.db.models import Count, Q
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Author, Book, Member, Loan
from .pagination import BookViewPagination
from .serializers import AuthorSerializer, BookSerializer, MemberSerializer, LoanSerializer, ExtendDueDateSerializer
from rest_framework.decorators import action
from django.utils import timezone
from .tasks import send_loan_notification

class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all().select_related('author')
    serializer_class = BookSerializer
    pagination_class = BookViewPagination

    @action(detail=True, methods=['post'])
    def loan(self, request, pk=None):
        book = self.get_object()
        if book.available_copies < 1:
            return Response({'error': 'No available copies.'}, status=status.HTTP_400_BAD_REQUEST)
        member_id = request.data.get('member_id')
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            return Response({'error': 'Member does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan = Loan.objects.create(book=book, member=member)
        book.available_copies -= 1
        book.save()
        send_loan_notification.delay(loan.id)
        return Response({'status': 'Book loaned successfully.'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def return_book(self, request, pk=None):
        book = self.get_object()
        member_id = request.data.get('member_id')
        try:
            loan = Loan.objects.get(book=book, member__id=member_id, is_returned=False)
        except Loan.DoesNotExist:
            return Response({'error': 'Active loan does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan.is_returned = True
        loan.return_date = timezone.now().date()
        loan.save()
        book.available_copies += 1
        book.save()
        return Response({'status': 'Book returned successfully.'}, status=status.HTTP_200_OK)

class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer

    @action(methods=['get'], detail=False, url_path='top-active')
    def top_active_members(self, request):
        members = self.get_queryset().annotate(active_loans=Count('loans', filter=Q(loans__is_returned=False))).order_by('active_loans')[:5]
        data = []
        for member in members:
            data.append({
                "id": member.id,
                "username": member.user.username,
                "active_loans": member.active_loans
            })
        return Response(data, status=status.HTTP_200_OK)
class LoanViewSet(viewsets.ModelViewSet):
    queryset = Loan.objects.all()
    serializer_class = LoanSerializer

    @action(methods=['post'], detail=True)
    def extend_due_date(self, request, pk=None):
        loan = self.get_object()

        # Check if the book has already been returned
        if loan.is_returned:
            return Response({'error': 'Active loan does not exist.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if the loan is already over due
        if loan.due_date < timezone.now().date():
            return Response({'error': "Loan is over Due"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate the request data. It is an integer and min_value > 0
        serializer = ExtendDueDateSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Update the Due date
        loan.due_date += timedelta(days=serializer.data['additional_days'])
        loan.save()

        return Response({'status': 'Loan extended successfully.', "due_date": loan.due_date}, status=status.HTTP_201_CREATED)