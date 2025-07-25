def get_event_data_based_on_link(data, link):
    return next((item for item in data if item.get('link') == link), None)
