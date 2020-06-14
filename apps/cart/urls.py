from django.urls import path
from cart.views import CartAddView, CartUpdateView, CartDeleteView, CartInfoView
urlpatterns = [
    path('add', CartAddView.as_view(), name='add'),
    path('', CartInfoView.as_view(), name='show'),
    path('update', CartUpdateView.as_view(), name='update'),
    path('delete', CartDeleteView.as_view(), name='delete'),
]
