from django.shortcuts import render

# Create your views here.


def foodtruck_list(request):
    """
    Display list of foodtrucks.
    Business logic is handled by JavaScript via API calls.
    """
    return render(request, 'foodtrucks/list.html')
