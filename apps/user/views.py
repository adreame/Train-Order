from django.shortcuts import render, redirect
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import View
from django.urls import reverse
from django.http import HttpResponse
from celery_tasks.tasks import send_register_active_email  # 导入celery发邮件的方法
from user.models import User, Address
from goods.models import GoodsSKU
from order.models import OrderInfo, OrderGoods
from django_redis import get_redis_connection
from django.core.paginator import Paginator
import re

# Create your views here.

def register(request):
    '''显示注册页面'''
    if request.method == 'GET':
        return render(request,'register.html')
    else:
        # 接收数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        cpassword = request.POST.get('cpwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 进行数据校验
        if not all([username, password, email]):
            # 数据不完整
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        # 进行密码校验
        if password != cpassword:
            render(request, 'register.html', {'errmsg': '密码不相同'})

        # 进行邮箱校验
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        # 进行协议校验
        if allow != 'on':
            render(request, 'register.html', {'errmsg': '请同意协议'})

        # 校验用户名是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在,可用
            user = None

        if user:
            # 用户名已存在
            return render(request, 'register.html', {'errmsg': '用户名已存在'})

        # 进行业务处理: 进行用户注册
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()

        # 返回应答,跳转到首页
        return redirect(reverse('goods:index'))


def register_handle(request):
    '''进行注册处理'''
    #接收数据
    username = request.POST.get('user_name')
    password = request.POST.get('pwd')
    cpassword = request.POST.get('cpwd')
    email = request.POST.get('email')
    allow = request.POST.get('allow')

    #进行数据校验
    if not all([username, password, email]):
        #数据不完整
        return render(request, 'register.html', {'errmsg':'数据不完整'})

    #进行密码校验
    if password != cpassword:
        render(request, 'register.html', {'errmsg':'密码不相同'})

    #进行邮箱校验
    if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
        return render(request, 'register.html', {'errmsg':'邮箱格式不正确'})

    #进行协议校验
    if allow != 'on':
        render(request, 'register.html', {'errmsg': '请同意协议'})

    #校验用户名是否重复
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        #用户名不存在,可用
        user = None

    if user:
        #用户名已存在
        return render(request, 'register.html', {'errmsg':'用户名已存在'})

    #进行业务处理: 进行用户注册
    user = User.objects.create_user(username, email, password)
    user.is_active = 0
    user.save()

    #返回应答,跳转到首页
    return redirect(reverse('goods:index'))


class RegisterView(View):
    '''使用类视图进行注册'''
    def get(self,request):
        '''显示注册页面'''
        return render(request,'register.html')

    def post(self,request):
        '''进行注册处理'''
        # 接收数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        cpassword = request.POST.get('cpwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 进行数据校验
        if not all([username, password, email]):
            # 数据不完整
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        # 进行密码校验
        if password != cpassword:
            render(request, 'register.html', {'errmsg': '密码不相同'})

        # 进行邮箱校验
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        # 进行协议校验
        if allow != 'on':
            render(request, 'register.html', {'errmsg': '请同意协议'})

        # 校验用户名是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在,可用
            user = None

        if user:
            # 用户名已存在
            return render(request, 'register.html', {'errmsg': '用户名已存在'})

        # 进行业务处理: 进行用户注册
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()

        # 发送激活邮件, 包含激活链接: http://127.0.0.1:8000/user/active/1
        # 激活链接需要包含用户身份信息, 并且把身份信息进行加密

        #加密用户身份信息, 生成激活token
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm':user.id}
        token = serializer.dumps(info)
        token = token.decode()

        # 发送邮件
        # subject = '天天生鲜欢迎信息'
        # message = ''
        # html_message = '<h1>%s, 欢迎您成为天天生鲜会员</h1>请点击以下链接激活您的账户<br/><a href="http://127.0.0.1:8000/user/active/%s">http://127.0.0.1:8000/user/active/%s</a>'%(username, token, token)
        # sender = settings.EMAIL_FROM
        # receiver = [email]
        #
        # send_mail(subject, message, sender, receiver, html_message=html_message)

        # 发送邮件
        # delay(收件人, 用户名, token)
        send_register_active_email.delay(email, username, token)  # 把任务放入队列

        # 返回应答,跳转到首页
        return redirect(reverse('goods:index'))

class ActiveView(View):
    '''用户激活'''
    def get(self, request, token):
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)
            # 获取待激活用户的id
            user_id = info['confirm']
            # 获取用户信息
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()

            #跳转到登陆页面
            return redirect(reverse('user:login'))

        except SignatureExpired as e:
            # 激活链接已过期
            return HttpResponse('激活链接已过期')


class LoginView(View):
    '''登录'''
    def get(self, request):
        '''显示登陆页面'''
        # 判断是否记住用户名
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''

        return render(request, 'login.html', {'username':username, 'checked':checked})

    def post(self,request):
        '''登录校验'''
        #接收数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')

        #校验数据
        if not all([username, password]):
            # 用户名和密码正确
            #数据不完整
            return render(request, 'login.html', {'errmsg':'数据不完整'})

        #进行业务处理: 用户校验
        user = authenticate(username=username, password=password)

        if user is not None:
            if user.is_active:
                # 用户已激活
                # 记录用户的登录状态
                login(request, user)
                # 获取登陆后要跳转的地址,如果有next则获取到next的值,如果无则给一个默认值reverse('goods:index')
                next_url = request.GET.get('next', reverse('goods:index'))
                # 跳转到首页
                response = redirect(next_url)
                # 判断是否记住用户名
                remember = request.POST.get('remember')

                if remember == 'on':
                    # 需要记住用户名
                    response.set_cookie('username', username, max_age=7*24*3600)
                else:
                    response.delete_cookie('username')
                return response
            else:
                # 账户未激活
                return render(request, 'login.html', {'errmsg': '账户未激活'})
        else:
            # 用户名或密码不正确
            return render(request, 'login.html', {'errmsg': '用户名或密码不正确'})


class LogoutView(View):
    '''退出登录'''
    def get(self,request):
        '''退出登录'''
        # 清除session信息
        logout(request)

        # 跳转到首页
        return redirect(reverse('goods:index'))

class UserInfoView(LoginRequiredMixin, View):
    '''用户中心-信息页'''
    def get(self,request):
        '''显示'''
        # page = 'user'
        # if request.user.is_authenticated:
        # 它们在每次请求中都会提供 request.user 属性。
        # 如果当前没有用户登录，这个属性将会被设置为 AnonymousUser ，否则将会被设置为 User 实例。

        # 获取用户的个人信息
        user = request.user
        address = Address.objects.get_default_address(user)

        # 获取用户的历史浏览记录
        # 获取链接的方法一
        # from  redis import StrictRedis
        # sr = StrictRedis(host='192.168.0.105', port='6379', db=6)
        # 获取链接的方法二
        con = get_redis_connection('default')

        history_key = 'history_%d'%user.id

        # 获取用户最新浏览的前五个商品id
        sku_ids = con.lrange(history_key, 0, 4)

        # 从数据库中查询商品详情信息
        goods_li = []
        for id in sku_ids:
            goods = GoodsSKU.objects.get(id=id)
            goods_li.append(goods)

        # 组织上下文
        context = {'page':'user', 'address':address, 'goods_li':goods_li}

        return render(request, 'user_center_info.html', context)

class UserOrderView(LoginRequiredMixin, View):
    '''用户中心-订单页'''
    def get(self, request, page):
        '''显示'''
        # page = 'order'
        # 获取用户订单信息
        user = request.user
        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')

        # 遍历获取订单商品的信息
        for order in orders:
            # 根据order_id查询订单商品的信息
            order_skus = OrderGoods.objects.filter(order_id=order.order_id)

            # 遍历order_skus计算商品的小计
            for order_sku in order_skus:
                # 计算小计
                amount = order_sku.count*order_sku.price

                # 动态给order_sku增加属性
                order_sku.amount = amount

            # 动态给order增加属性
            order.order_status_name = OrderInfo.ORDER_STATUS[order.order_status]
            order.order_skus = order_skus

        # 分页
        paginator = Paginator(orders, 1)

        # 获取page页的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1

        if page > paginator.num_pages:
            page = 1

        # 获取第page页的Page实例对象
        order_page = paginator.page(page)

        # todo: 页码的控制页面上最多显示5页
        # 页码不足5页显示所有页面
        # 当前页为前三页,显示前五页
        # 当前页为后三页,显示后五页
        # 否则显示当前页前两页和后两页
        num_pages = paginator.num_pages

        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif page > num_pages - 3:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        # 组织上下文
        context = {
            'order_page':order_page,
            'pages':pages,
            'page': 'order',

        }

        return render(request, 'user_center_order.html', context)


class AddressView(LoginRequiredMixin, View):
    '''用户中心-地址页'''
    def get(self,request):
        '''显示'''
        # page = 'address'

        # 获取用户的默认收货地址
        # 获取用户登陆的user对象
        user = request.user

        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     # 不存在默认收获地址
        #     address = None
        address = Address.objects.get_default_address(user)

        return render(request, 'user_center_site.html', {'page':'address', 'address':address})

    def post(self,request):
        '''地址添加'''
        # 接收数据
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')

        # 校验数据
        if not all([receiver, addr, phone]):
            return render(request, 'user_center_site.html', {'errmsg':'数据不完整'})

        # 手机号校验
        if not re.match(r'^1[3|4|5|7|8][0-9]{9}$', phone):
            return render(request, 'user_center_site.html', {'errmsg': '手机号格式错误'})

        # 进行业务处理: 添加地址
        #如果用户已存在默认收货地址,不作为默认收获地址,否则作为默认收货地址
        # 获取用户登陆的user对象
        user = request.user

        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     # 不存在默认收获地址
        #     address = None

        address = Address.objects.get_default_address(user)

        if address:
            is_default = False
        else:
            is_default = True

        # 添加地址
        Address.objects.create(user=user, receiver=receiver, addr=addr, zip_code=zip_code, phone=phone, is_default=is_default)

        # 返回应答,刷新地址
        return redirect(reverse('user:address'))  # get请求方式

