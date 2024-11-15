def _create_field_transform(field_name):
    return {
        f"{field_name}": {
            "$arrayToObject": {
                "$map": {
                    "input": {"$objectToArray": f"${field_name}"},
                    "as": "item",
                    "in": {"k": "$$item.k", "v": "$$item.v.counts"},
                }
            }
        },
        f"unique_{field_name}": {
            "$arrayToObject": {
                "$map": {
                    "input": {"$objectToArray": f"${field_name}"},
                    "as": "item",
                    "in": {
                        "k": "$$item.k",
                        "v": {"$size": {"$setUnion": ["$$item.v.ips"]}},
                    },
                }
            }
        },
    }


def get_stats_pipeline(short_code):
    fields = ["browser", "os_name", "country", "referrer"]
    add_fields = {}
    for field in fields:
        add_fields |= _create_field_transform(field)

    return [
        {"$match": {"_id": short_code}},
        {
            "$project": {
                "url": 1,
                "browser": {"$ifNull": ["$browser", {}]},
                "os_name": {"$ifNull": ["$os_name", {}]},
                "country": {"$ifNull": ["$country", {}]},
                "referrer": {"$ifNull": ["$referrer", {}]},
                "total_unique_clicks": {"$size": "$ips"},
                "total-clicks": {"$ifNull": ["$total-clicks", 0]},
                "max-clicks": {"$ifNull": ["$max-clicks", None]},
                "expiration-time": {"$ifNull": ["$expiration-time", None]},
                "password": {"$ifNull": ["$password", None]},
                "short_code": {"$ifNull": ["$short_code", None]},
                "last-click-browser": {"$ifNull": ["$last-click-browser", None]},
                "last-click-os": {"$ifNull": ["$last-click-os", None]},
                "last-click-country": {"$ifNull": ["$last-click-country", None]},
                "block-bots": {"$ifNull": ["$block-bots", False]},
                "bots": {"$ifNull": ["$bots", {}]},
                "counter": {"$ifNull": ["$counter", {}]},
                "unique_counter": {"$ifNull": ["$unique_counter", {}]},
                "average_redirection_time": {
                    "$ifNull": ["$average_redirection_time", 0]
                },
                "creation-date": {"$ifNull": ["$creation-date", None]},
                "creation-time": {"$ifNull": ["$creation-time", None]},
                "last-click": {"$ifNull": ["$last-click", None]},
            }
        },
        {"$addFields": add_fields},
    ]
