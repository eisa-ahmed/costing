# -*- coding: utf-8 -*-
{
    'name': "Costing (CMT)",
    'summary': """
        Managing Costing of Operations: Cut, Make, Trim.
        """,
    'description': """
        Managing Costing of Operations: Cut, Make, Trim.
    """,
    'author': "EisaA",
    'website': "https://www.fiverr.com/eisaahmed63",
    'category': 'Manufacturing',
    'version': '1.1',
    'depends': ['base', 'product', 'uom', 'mrp', 'hr', 'purchase'],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/inherited_views.xml',
    ],
    'license': 'OEEL-1',
}
