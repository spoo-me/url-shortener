def get_stats_pipeline(short_code):
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
        {
            "$addFields": {
                "unique_browser": {
                    "$arrayToObject": {
                        "$map": {
                            "input": {"$objectToArray": "$browser"},
                            "as": "item",
                            "in": {
                                "k": "$$item.k",
                                "v": {"$size": {"$setUnion": ["$$item.v.ips"]}},
                            },
                        }
                    }
                },
                "unique_os_name": {
                    "$arrayToObject": {
                        "$map": {
                            "input": {"$objectToArray": "$os_name"},
                            "as": "item",
                            "in": {
                                "k": "$$item.k",
                                "v": {"$size": {"$setUnion": ["$$item.v.ips"]}},
                            },
                        }
                    }
                },
                "unique_country": {
                    "$arrayToObject": {
                        "$map": {
                            "input": {"$objectToArray": "$country"},
                            "as": "item",
                            "in": {
                                "k": "$$item.k",
                                "v": {"$size": {"$setUnion": ["$$item.v.ips"]}},
                            },
                        }
                    }
                },
                "unique_referrer": {
                    "$arrayToObject": {
                        "$map": {
                            "input": {"$objectToArray": "$referrer"},
                            "as": "item",
                            "in": {
                                "k": "$$item.k",
                                "v": {"$size": {"$setUnion": ["$$item.v.ips"]}},
                            },
                        }
                    }
                },
                "browser": {
                    "$arrayToObject": {
                        "$map": {
                            "input": {"$objectToArray": "$browser"},
                            "as": "item",
                            "in": {"k": "$$item.k", "v": "$$item.v.counts"},
                        }
                    }
                },
                "os_name": {
                    "$arrayToObject": {
                        "$map": {
                            "input": {"$objectToArray": "$os_name"},
                            "as": "item",
                            "in": {"k": "$$item.k", "v": "$$item.v.counts"},
                        }
                    }
                },
                "country": {
                    "$arrayToObject": {
                        "$map": {
                            "input": {"$objectToArray": "$country"},
                            "as": "item",
                            "in": {"k": "$$item.k", "v": "$$item.v.counts"},
                        }
                    }
                },
                "referrer": {
                    "$arrayToObject": {
                        "$map": {
                            "input": {"$objectToArray": "$referrer"},
                            "as": "item",
                            "in": {"k": "$$item.k", "v": "$$item.v.counts"},
                        }
                    }
                },
            }
        },
    ]
