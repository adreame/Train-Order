from django.shortcuts import render, redirect, reverse
from django.views.generic import View
from django.http import JsonResponse
from django_redis import get_redis_connection
from order.models import OrderInfo, OrderGoods
from goods.models import GoodsSKU
from user.models import Address
from datetime import datetime
from django.db import transaction  # 事务
from django.contrib.auth.mixins import LoginRequiredMixin
from alipay import AliPay
from django.conf import settings
from django.core.cache import cache
import os
# Create your views here.


class OrderPlaceView(LoginRequiredMixin, View):
    '''提交订单页'''
    def post(self,request):
        '''显示提交订单页'''
        # 获取登录用户
        user = request.user
        # 获取由购物车表单提交的数据sku_ids
        sku_ids = request.POST.getlist('sku_ids')

        #校验参数
        if not sku_ids:
            # 跳转到购物车页面
            return redirect(reverse('cart:show'))

        # 链接redis获取购物车中的信息
        conn = get_redis_connection('default')
        cart_key = 'cart_%d'%user.id

        skus = []
        total_count = 0
        total_price = 0
        # 遍历sku_ids,获取用户购买的商品
        for sku_id in sku_ids:
            # 根据商品id获取商品信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 获取用户要购买的商品数量
            count = conn.hget(cart_key, sku_id)
            # 计算商品的总价
            amount = sku.price*int(count)
            # 动态给sku增加count属性
            sku.count = int(count)
            # 动态给sku增加amount属性
            sku.amount = amount
            # 追加
            skus.append(sku)
            # 计算购物车中商品总价和总数
            total_count += int(count)
            total_price += amount

        # 运费
        transit_price = 10  # 实际开发,属于一个子系统

        # 实付款
        total_pay = transit_price + total_price

        # 获取用户收货地址
        addrs = Address.objects.filter(user=user)

        # 组织上下文
        sku_ids = ','.join(sku_ids)
        context = {
            'skus':skus,
            'total_count':total_count,
            'total_price':total_price,
            'total_pay':total_pay,
            'transit_price':transit_price,
            'sku_ids':sku_ids,
            'addrs':addrs}

        return render(request, 'place_order.html', context)


# mysql事务:原子性, 稳定性, 隔离性, 可靠性
class OrderCommit(View):
    '''订单创建'''
    def post(self, request):
        '''订单创建'''
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated:
            # 用户未登录
            return JsonResponse({'res':0, 'errmsg':'用户未登录'})
        # 接收数据
        addr_id = request.POST.get('addr_id')
        sku_ids = request.POST.get('sku_ids')  # 1,3,2
        pay_method = request.POST.get('pay_method')

        # 进行数据校验
        if not all([addr_id, sku_ids, pay_method]):
            return JsonResponse({'res':1, 'errmsg':'数据不完整'})

        # 校验地址
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res':2, 'errmsg':'地址不存在'})

        # 校验支付方式
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res':3, 'errmsg':'支付方式非法'})

        # todo: 创建订单核心业务
        # 组织订单id: 20191109163030+user.id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)

        # 运费
        transit_price = 10

        # 总数目和总金额
        total_price = 0
        total_count = 0

        # todo: 设置mysql事务保存点
        save_id = transaction.savepoint()

        try:
            # todo: 向df_order_info中添加一条记录
            order = OrderInfo.objects.create(
                order_id=order_id,
                user=user,
                addr=addr,
                pay_method=pay_method,
                total_count=total_count,
                total_price=total_price,
                transit_price=transit_price,
            )

            # todo: 用户订单中有几件商品就向df_order_goods中加入几条数据
            conn = get_redis_connection('default')
            cart_key = 'cart_%d'%user.id

            sku_ids = sku_ids.split(',')

            for sku_id in sku_ids:
                try:
                    sku = GoodsSKU.objects.get(id=sku_id)
                    # todo: 解决高并发出现的问题
                    # todo: 乐观锁: 不加锁在商品信息更新时进行库存校验
                    # update df_goods_sku set stock=new_stock, sales=new_sales
                    # where id=sku_id and stock=orgin_stock;

                    # 需要更该mysql 事务隔离等级为 read commited
                    # orgin_stock = sku.stock  # 记录查到的库存量
                    # new_stock = orgin_stock - int(count)
                    # new_sales = sku.sales - int(count)
                    # res = GoodsSKU.objects.filter(id=sku_id, stock=orgin_stock).update(stock=new_stock, salws=new_sales)
                    # if res == 0:
                    #     transaction.savepoint_rollback(save_id)
                    #     return JsonResponse({'res':7, 'errmsg':'下单失败'})

                    # todo: 加悲观锁:同一时间只有一个用户获取商品信息
                    # sku = GoodsSKU.objects.select_for_update().get(id=sku_id)  # 悲观锁
                except:
                    # 商品不存在
                    # 事务回滚
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res':4, 'errmsg':'商品不存在'})

                # 从redis中获取商品数量
                count = conn.hget(cart_key, sku_id)

                # todo: 判断库存
                if int(count) > sku.stock:
                    # 库存不足
                    # 事务回滚
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res':6, 'errmsg':'商品库存不足'})

                # todo: 更新商品的库存和销量
                sku.stock -= int(count)
                sku.sales += int(count)
                sku.save()

                # todo: 向df_order_goods表中加入数据
                OrderGoods.objects.create(
                    order=order,
                    sku=sku,
                    count=count,
                    price=sku.price,
                )

                # 计算商品总价和总数
                amount = sku.price*int(count)
                total_count += int(count)
                total_price += amount

            # todo: 更新df_order_info表中的数据
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            # 事务回滚

            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res':7, 'errmsg':'下单失败'})

         # todo: 提交事务
        transaction.savepoint_commit(save_id)

        # todo: 删除购物车记录
        conn.hdel(cart_key, *sku_ids)

        # 返回应答
        return JsonResponse({'res':5, 'message':'创建成功'})


class OrderPayView(View):
    def post(self,request):
        #判断用户是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({"res":0,"errmsg":"用户未登录"})
        #接收参数
        order_id = request.POST.get('order_id')
        #校验参数
        if not order_id:
            return JsonResponse({"res":1,"errmsg":"无效的订单id"})
        try:
            #order_id:订单id，user：用户，pay_method=3:支付方式(支付宝),order_status:订单状态(未支付)
            order = OrderInfo.objects.get(order_id=order_id,user=user,pay_method=3,order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({"res":2,"errmsg":"订单错误"})
        #业务处理:使用Python sdk调用支付宝的支付接口
        alipay = AliPay(
            appid="2016101700708720",   #APPID
            app_notify_url=None,  # 默认回调url,可以传也可以不传
            app_private_key_path=os.path.join(settings.BASE_DIR,"apps/order/app_private_key.pem"), #私钥的路径
            alipay_public_key_path=os.path.join(settings.BASE_DIR,"apps/order/alipay_public_key.pem"),#支付宝公钥的路径
            sign_type="RSA2",  # RSA 或者 RSA2，签名的算法
            debug = True  # 默认False，沙箱环境改成True
        )
        #借助alipay对象，向支付宝发起支付请求
        #电脑网站支付，需要跳转到https://openapi.alipaydev.com/gateway.do?+order_string
        total_pay = order.total_price + order.transit_price #订单总金额
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,  #订单id
            total_amount=str(total_pay), #支付宝总金额
            subject="天天生鲜%s"%order_id, #订单标题
            return_url=None,
            notify_url=None
        )
        #返回应答
        pay_url = "https://openapi.alipaydev.com/gateway.do?"+order_string
        return JsonResponse({"res":3,"pay_url":pay_url})


#查看订单支付的结果
#ajax post
#前端传递参数：订单id(order_id)
#/order/check
class CheckPayView(View):
    def post(self,request):
        #用户是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({"res":0,"errmsg":"用户未登录"})
        #接收参数
        order_id = request.POST.get("order_id")

        #校验参数
        if not order_id:
            return JsonResponse({"res":1,"errmsg":"无效的订单id"})
        try:
            order = OrderInfo.objects.get(order_id=order_id,user=user,pay_method=3,order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({"res":2,"errmsg":"订单错误"})
        #业务处理：使用python sdk调用支付宝的支付接口
        #初始化
        alipay = AliPay(
            appid="2016101700708720",  # APPID
            app_notify_url=None,  # 默认回调url,可以传也可以不传
            app_private_key_path=os.path.join(settings.BASE_DIR, "apps/order/app_private_key.pem"),  # 私钥的路径
            alipay_public_key_path=os.path.join(settings.BASE_DIR, "apps/order/alipay_public_key.pem"),  # 支付宝公钥的路径
            sign_type="RSA2",  # RSA 或者 RSA2，签名的算法
            debug=True  # 默认False，沙箱环境改成True
        )
        while True:
            response = alipay.api_alipay_trade_query(order_id)

            # response = {
            #     "alipay_trade_query_response": {
            #         "trade_no": "2017032121001004070200176844",
            #         "code": "10000",
            #         "invoice_amount": "20.00",
            #         "open_id": "20880072506750308812798160715407",
            #         "fund_bill_list": [
            #             {
            #                 "amount": "20.00",
            #                 "fund_channel": "ALIPAYACCOUNT"
            #             }
            #         ],
            #         "buyer_logon_id": "csq***@sandbox.com",
            #         "send_pay_date": "2017-03-21 13:29:17",
            #         "receipt_amount": "20.00",
            #         "out_trade_no": "out_trade_no15",
            #         "buyer_pay_amount": "20.00",
            #         "buyer_user_id": "2088102169481075",
            #         "msg": "Success",
            #         "point_amount": "0.00",
            #         "trade_status": "TRADE_SUCCESS",
            #         "total_amount": "20.00"
            #     },
            code = response.get("code")
            #如果返回码为10000和交易状态为交易支付成功
            if code == "10000" and response.get("trade_status") == "TRADE_SUCCESS":
                #支付成功
                #获取支付宝交易号
                trade_no = response.get("trade_no")
                #更新订单状态
                order.trade_no = trade_no
                order.order_status = 4  # 待评价
                order.save()
                return JsonResponse({"res":3,"message":"支付成功"})
            #返回码为40004 或 交易状态为等待买家付款
            elif code == "40004" or (response.get("trade_status") == "WAIT_BUYER_PAY"):
                #等待买家付款
                #业务处理失败，可能一会就会成功
                import time
                time.sleep(5)
                continue
            else:
                #支付出错
                return JsonResponse({"res":4,"errmsg":"支付失败"})


class CommentView(LoginRequiredMixin, View):
    """订单评论"""
    def get(self, request, order_id):
        """提供评论页面"""
        user = request.user

        # 校验数据
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("orders:info"))

        # 根据订单的状态获取订单的状态标题
        order.status_name = OrderInfo.ORDER_STATUS[order.order_status]

        # 获取订单商品信息
        order_skus = OrderGoods.objects.filter(order_id=order_id)

        for order_sku in order_skus:
            # 获取商品总价
            amount = order_sku.price * order_sku.count
            # 动态给order_sku增加属性
            order_sku.amount = amount
        # 动态给order增加属性
        order.order_skus = order_skus

        return render(request, "order_comment.html", {"order": order})

    def post(self, request, order_id):
        """处理评论内容"""
        user = request.user
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("orders:info"))

        # 获取评论条数
        total_count = request.POST.get("total_count")
        total_count = int(total_count)

        for i in range(1, total_count + 1):
            sku_id = request.POST.get("sku_%d" % i)
            content = request.POST.get('content_%d' % i, '')
            try:
                order_goods = OrderGoods.objects.get(order=order, sku_id=sku_id)
            except OrderGoods.DoesNotExist:
                continue

            order_goods.comment = content
            order_goods.save()

        order.order_status = 5  # 已完成
        order.save()

        return redirect(reverse('user:order', kwargs={"page": 1}))





















