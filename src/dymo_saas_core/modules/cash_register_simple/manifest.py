manifest = {
    "key": "cash_register_simple",
    "name": "Caisse Simple",
    "description": "Module pilote pour gérer des ventes simples et clôtures de caisse.",
    "version": "1.0.0",
    "minimum_core_version": "1.0.0",
    "category": "business",
    "is_core": False,
    "is_paid_addon": True,
    "routes_prefix": "/api/v1/app/cash-register",
    "dependencies": [],
    "permissions": [
        {"code": "cash_register_simple.sales.view", "name": "View Sales", "description": "Can view sales"},
        {"code": "cash_register_simple.sales.create", "name": "Create Sales", "description": "Can register new sales"},
        {"code": "cash_register_simple.sales.cancel", "name": "Cancel Sales", "description": "Can cancel registered sales"},
        {"code": "cash_register_simple.closures.view", "name": "View Closures", "description": "Can view day closures"},
        {"code": "cash_register_simple.closures.create", "name": "Create Closures", "description": "Can close the day register"},
        {"code": "cash_register_simple.reports.view", "name": "View Reports", "description": "Can view daily sales reports"}
    ],
    "limits": [
        {
            "metric_key": "cash_register_simple.sales.monthly",
            "limit_value": 500,
            "period": "monthly",
            "overage_allowed": False
        },
        {
            "metric_key": "cash_register_simple.cashiers.max",
            "limit_value": 5,
            "period": "monthly",
            "overage_allowed": False
        }
    ],
    "events": [
        {"event_type": "cash_register_simple.sale_created", "description": "Fired when a new sale is created"},
        {"event_type": "cash_register_simple.sale_cancelled", "description": "Fired when a sale is cancelled"},
        {"event_type": "cash_register_simple.day_closed", "description": "Fired when a day register is closed"}
    ],
    "settings": {}
}
