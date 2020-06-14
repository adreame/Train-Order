from django.contrib import admin
from django.core.cache import cache
from goods.models import GoodsType, IndexGoodsBanner, IndexTypeGoodsBanner, IndexPromotionBanner, GoodsSKU, Goods, GoodsImage
from celery_tasks.tasks import generate_static_index_html
# Register your models here.

class BaseModelAdmin(admin.ModelAdmin):
    """当后台数据库数据改动时使celery重新生成静态首页页面"""
    def save_model(self, request, obj, form, change):
        """当更新或者新增数据时调用"""
        super().save_model(request, obj, form, change)
        # 发出任务，让celery worker重新生成静态首页
        generate_static_index_html.delay()

        # 清除首页的缓存数据
        cache.delete("index_page_data")

    def delete_model(self, request, obj):
        """当删除数据时调用"""
        super().delete_model(request, obj)
        generate_static_index_html.delay()

        # 清除首页的缓存数据
        cache.delete("index_page_data")


class GoodsAdmin(BaseModelAdmin):
    list_display = ['name']


class GoodsSKUAdmin(BaseModelAdmin):
    list_display = ['name']


class GoodsTypeAdmin(BaseModelAdmin):
    list_display = ['name']


class IndexGoodsBannerAdmin(BaseModelAdmin):

    list_display = ['sku']


class IndexTypeGoodsBannerAdmin(BaseModelAdmin):
    list_display = ['type']


class IndexPromotionBannerAdmin(BaseModelAdmin):
    list_display = ['name']


admin.site.register(Goods, GoodsAdmin)
admin.site.register(GoodsSKU, GoodsSKUAdmin)
admin.site.register(GoodsType, GoodsTypeAdmin)
admin.site.register(IndexGoodsBanner, IndexGoodsBannerAdmin)
admin.site.register(IndexTypeGoodsBanner, IndexTypeGoodsBannerAdmin)
admin.site.register(IndexPromotionBanner, IndexPromotionBannerAdmin)
