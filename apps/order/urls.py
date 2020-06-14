from django.urls import path, re_path
from order.views import OrderPlaceView, OrderCommit, OrderPayView, CheckPayView, CommentView
urlpatterns = [
    path('place', OrderPlaceView.as_view(), name='place'),
    path('commit', OrderCommit.as_view(), name='commit'),
    path('pay', OrderPayView.as_view(), name='pay'),  # 订单支付
    path('check', CheckPayView.as_view(), name='check'),
    re_path(r'^comment/(?P<order_id>\d+)$', CommentView.as_view(), name='comment')
]
