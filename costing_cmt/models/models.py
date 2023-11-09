# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, date
import calendar


def get_month_ends():
    # Get the current date
    current_date = date.today()

    # Calculate the first day of the current month
    first_day_of_month = current_date.replace(day=1)

    # Calculate the last day of the current month
    _, last_day_of_month = calendar.monthrange(current_date.year, current_date.month)

    # Create datetime objects for the first and last days
    first_date_of_month = datetime(first_day_of_month.year, first_day_of_month.month, first_day_of_month.day)
    last_date_of_month = datetime(current_date.year, current_date.month, last_day_of_month, 23, 59, 59)
    return first_date_of_month, last_date_of_month


class OverheadRecord(models.Model):
    _name = 'overhead.record'
    _description = 'Overhead Record'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'overhead_id'

    overhead_id = fields.Many2one('overhead.name', string='Name', required=True)
    cost = fields.Monetary(string='Cost', currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    month = fields.Selection([
        ('01', 'January'),
        ('02', 'February'),
        ('03', 'March'),
        ('04', 'April'),
        ('05', 'May'),
        ('06', 'June'),
        ('07', 'July'),
        ('08', 'August'),
        ('09', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December'),
    ], string='Month', default=lambda self: fields.Date.today().strftime('%m'))
    year = fields.Char(string='Year', default=lambda self: fields.Date.today().strftime('%Y'), readonly=True)


class OverheadRecordName(models.Model):
    _name = 'overhead.name'
    _description = 'Overhead Name'

    name = fields.Char(required=True)


class ProductTemplateInherit(models.Model):
    _inherit = 'product.template'

    costing_product_type = fields.Selection([
        ('shell', 'Shell Fabric'),
        ('lining', 'Lining Fabric'),
        ('zipper', 'Zipper'),
        ('button', 'Button'),
        ('embellishment', 'Embellishment')
    ], string="Product Type")
    detailed_type = fields.Selection(default='product')


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    expected_cmt = fields.Monetary(related='bom_id.cmt_cost', store=True)
    cmt_cost = fields.Monetary(string='CMT Cost', compute='_compute_cmt_cost', store=True)
    total_cost_overheads_incl = fields.Monetary(string='Total Cost Overheads Incl.', compute='_compute_cmt_cost',
                                                store=True)
    product_id = fields.Many2one(string='Style')

    @api.depends('workorder_ids.duration', 'workorder_ids.costs_hour', 'move_raw_ids.product_id.standard_price',
                 'move_raw_ids.product_qty', 'move_raw_ids.product_uom', 'date_finished')
    def _compute_cmt_cost(self):
        for record in self:
            # Existing CMT computation for operations
            cmt_operations = sum(
                workorder.responsible_id.hourly_cost * (workorder.duration / 60) for workorder in record.workorder_ids)

            # Component cost computation from Bill of Materials
            components_cost = record.bom_id.components_cost if record.bom_id else 0

            # Total CMT
            cmt_cost = cmt_operations + components_cost
            record.cmt_cost = cmt_cost
            # Calculate with current months overheads share
            if record.date_finished:
                month = record.date_finished.strftime('%m')
                year = record.date_finished.strftime('%Y')

                total_cost = sum(self.env['overhead.record'].search([
                    ('month', '=', month),
                    ('year', '=', year)
                ]).mapped('cost'))

                # Calculate the share by dividing the overhead costs by the number of MOs finished this month
                num_finished_mos = self.env['mrp.production'].search_count([
                    ('date_finished', '>=', get_month_ends()[0]),
                    ('date_finished', '<=', get_month_ends()[1]),
                    ('state', '=', 'done')
                ])

                if num_finished_mos > 0:
                    share = total_cost / num_finished_mos
                else:
                    share = total_cost

                # Update the total_cost_overheads_incl field
                record.total_cost_overheads_incl = cmt_cost + share
            else:
                record.total_cost_overheads_incl = 0


class MrpBomInherit(models.Model):
    _inherit = 'mrp.bom'

    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    components_cost = fields.Monetary(string='Components Cost', compute='_compute_costs', store=True)
    cmt_cost = fields.Monetary(string='Estimated CMT Cost', compute='_compute_costs', store=True,
                               help="""This Cost is an estimate based on the components costs and costs of operations specified for this Bill of Materials.""")

    @api.depends('operation_ids.time_cycle', 'operation_ids.workcenter_id.costs_hour',
                 'bom_line_ids.product_id.standard_price', 'bom_line_ids.product_qty', 'bom_line_ids.product_uom_id')
    def _compute_costs(self):
        for record in self:
            # Existing CMT computation for operations
            cmt_operations = sum(
                workorder.responsible_id.hourly_cost * (workorder.time_cycle / 60) for workorder in
                record.operation_ids)
            # Component cost computation from manufacturing order lines
            components_cost = 0
            for move in record.bom_line_ids:
                components_cost += move.price * move.product_qty
            # Total Costs
            record.components_cost = components_cost
            record.cmt_cost = cmt_operations + components_cost


class MrpWorkOrder(models.Model):
    _inherit = 'mrp.workorder'

    product_id = fields.Many2one(string='Style')
    responsible_id = fields.Many2one('hr.employee', string='Responsible', required=True,
                                     related='operation_id.responsible_id')


class MrpRoutingWorkCenter(models.Model):
    _inherit = 'mrp.routing.workcenter'

    responsible_id = fields.Many2one('hr.employee', string='Responsible', required=True, store=True)


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    product_id = fields.Many2one(domain=[('costing_product_type', '!=', False)])
    costing_product_type = fields.Selection(related='product_id.costing_product_type', string='Category')
    price = fields.Float(related='product_id.standard_price', store=True, readonly=False, required=True)
    subtotal = fields.Float(compute='_compute_subtotal')

    @api.depends('price', 'product_qty')
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = rec.price * rec.product_qty


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    hourly_cost = fields.Monetary(currency_id=lambda self: self.env.company.currency_id, required=True)
