import scrapy


class WebcrawlerItem(scrapy.Item):
    # define the fields for your item here like:
    url = scrapy.Field()
    title = scrapy.Field()
    text = scrapy.Field()
    images = scrapy.Field()
    links = scrapy.Field()
    word_count = scrapy.Field()
    image_count = scrapy.Field()