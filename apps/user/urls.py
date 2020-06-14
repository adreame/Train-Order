from django.urls import path, re_path
from django.contrib.auth.decorators import login_required  # 登录装饰器判断用户是否登录
from user import views
from user.views import RegisterView, ActiveView, LoginView, UserInfoView, UserOrderView, AddressView, LogoutView
urlpatterns = [
    #path('register', views.register, name='register'),  #注册
    #path('register_handle', views.register_handle, name='register_handle'),  #进行注册处理
    path('register', RegisterView.as_view(), name='register'),  #注册
    re_path(r'^active/(?P<token>.*)$', ActiveView.as_view(), name='active'), #用户激活
    path('login', LoginView.as_view(), name='login'),  #显示登录页面
    path('logout', LogoutView.as_view(), name='logout'),  #注销登录

    # path('', login_required(UserInfoView.as_view()), name='user'),  #用户中心-信息页
    # path('order', UserOrderView.as_view(), name='order'),  #用户中心-订单页
    # path('address', AddressView.as_view(), name='address'),  #用户中心-地址页

    path('', UserInfoView.as_view(), name='user'),  # 用户中心-信息页
    re_path(r'^order/(?P<page>\d+)$', UserOrderView.as_view(), name='order'),  # 用户中心-订单页
    path('address', AddressView.as_view(), name='address'),  # 用户中心-地址页

]
