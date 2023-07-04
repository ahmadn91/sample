# -*- coding: utf-8 -*-


"""

This code defines a model class called "Delivery" that inherits from several other models in the Odoo framework. It represents a delivery entity and contains various fields and methods related to deliveries.

The fields in the "Delivery" class represent different attributes of a delivery, such as name, status, date, volume information, assigned slots, technicians, customers, etc. Some fields are computed based on the values of other fields.

The class includes methods for performing various operations on deliveries, such as setting slots to delivered or cancelled, reallocation of deliveries, updating related objects when the delivery date changes, computing the list of customers, refreshing vehicle assignments, and more. These methods are triggered under certain conditions or by user actions.

Additionally, there are computed fields that generate HTML content for displaying information in the user interface, and methods for redirecting to other views or returning views for specific actions.

Overall, this code provides a model representation of a delivery entity and defines its behavior and functionality within the Odoo framework.

"""
from cmath import e
from inspect import trace
from odoo import models, fields, api
from odoo.exceptions import UserError
import datetime
from os import urandom
import hashlib
import uuid
from typing import Union, Optional, Dict, Type
from odoo.addons.sale.models.sale_order import SaleOrder



class Delivery(models.Model):
    _name = 'logistic.delivery'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Delivery'
    _order = 'name'

    _sql_constraints = [('unique_name', 'unique(name)',
                         'Name field should be unique')]

    VALID_STATUSES_SLOT_STATUS_CHANGE = ['scheduled', 'loaded']

    STATUS = [("scheduled", "Scheduled"),
              ("loaded", "Loaded"),
              ("in_transit", "In Transit"),
              ("fulfilled", "Fulfilled"),
              ("cancelled", "Cancelled")]

    guid = fields.Char(
        string="GUID",
        readonly=True,
        copy=False,
        index=True
    )

    name = fields.Char(
        string='Name',
        required=True,
        readonly=True,
        copy=False,
        index=True
    )

    color = fields.Integer(
        string="Color",
        compute="_compute_color",
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.user.company_id.id,
    )

    vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Vehicle",
        track_visibility="onchange",
    )

    date = fields.Date(
        string="Date",
        track_visibility="onchange",

    )

    status = fields.Selection(
        STATUS,
        string="Status",
        readonly=True,
        default="scheduled",
        track_visibility="onchange",
    )

    total_volume = fields.Float(
        string="Total Volume",
        compute="_compute_total_volume"
    )

    delivered_volume = fields.Float(
        string="Delivered Volume",
        compute="_compute_delivered_volume"
    )

    remaining_volume = fields.Float(
        string="Remaining Volume to be delivered",
        compute="_compute_remaining_volume"
    )

    fullfilled_date = fields.Datetime(
        string="Fullfilled Date",
        readonly=True,
        track_visibility="onchange",
    )

    slot_ids = fields.One2many("logistic.slot",
                               "delivery_id",
                               string="Slot",
                               track_visibility="onchange",
                               )

    all_day = fields.Boolean(
        string="All Day",
        default=True
    )

    trip_start_time = fields.Datetime(
        string="Trip Start Time",
        track_visibility="onchange",
    )

    trip_end_time = fields.Datetime(
        string="Trip End Time",
        track_visibility="onchange",
    )

    trip_duration = fields.Float(
        string="Trip Duration",
        compute="_compute_trip_duration"
    )

    volume_loss = fields.Float(
        string="Volume Loss",
        compute="_compute_volume_loss"
    )

    volume_loss_percentage = fields.Float(
        string="Volume Loss Percentage",
        compute="_compute_volume_loss_percentage"
    )

    progress = fields.Float(
        string="Progress",
        compute="_compute_progress",
        digits=(16, 4)
    )

    active = fields.Boolean(
        string="Active",
        default=True
    )

    sale_order_ids = fields.Many2many(
        comodel_name="sale.order",
        relation="delivery_sale_order_rel",
        column1="delivery_id",
        column2="sale_order_id",
        string="Sale Orders",
        compute="_compute_sale_order_ids",
        store=True
    )

    sale_orders_count = fields.Integer(
        string="Sale Orders",
        compute="_compute_sale_orders_count"
    )

    cancelled_date = fields.Datetime(
        string="Cancelled Date",
        track_visibility="onchange",
    )

    
    delivery_count = fields.Integer(
        "Delivery Count",
        compute="_compute_delivery_count"
    )

    zone_id = fields.Many2one(
        "logistic.zone",
        string="Zone",
        compute="_compute_zone_id",
        store=True
    )

    task_count = fields.Integer(
        string="Task Count",
        compute="_compute_task_count"
    )

    district_ids = fields.Many2many(
        "logistic.district",
        "delivery_district_rel",
        "delivery_id",
        "district_id",
        string="Districts",
        compute="_compute_district_ids"
    )

    cluster_id = fields.Many2one(
        "logistic.cluster",
        string="Cluster",
        related="zone_id.cluster_id",
        store=True
    )

    zone_center_lon = fields.Float(
        related="zone_id.center_lon"
    )

    zone_center_lat = fields.Float(
        related="zone_id.center_lat"
    )

    # fires when slot_ids has slot in different cluster
    mismatched_zones = fields.Boolean(
        string="Mismatched Zones"
    )

    all_techs_assigned = fields.Boolean(
        string="All Techs Assigned",
        compute="_compute_all_techs_assigned",
        store=True
    )

    info = fields.Html(
        string="Info",
        compute="_compute_info"
    )
    side_button_info = fields.Html(
        string="Side Button Info",
        compute="_compute_side_button_info"
    )
    total_assembly = fields.Float(
        string="Total Assembly",
        compute="_compute_total_assembly"
    )

    left_side_panel_assembly_info = fields.Html(
        string="Assembly Info",
        compute="_compute_assembly_info"
    )

    left_side_panel_assembly_info_static = fields.Html(
        string="Assemby info static",
        compute="_compute_assembly_info_static"
    )

    fsm_ids = fields.Many2many(
        "project.task",
        "delivery_fsm_rel",
        "delivery_id",
        "fsm_id",
        string="FSM",
        compute="_compute_fsm_ids"
    )

    tech_ids = fields.Many2many(
        "res.users",
        "delivery_tech_rel",
        "delivery_id",
        "tech_id",
        string="Technicians",
        compute="_compute_tech_ids"
    )
    customers = fields.Char(
        string="Customers",
        compute="_compute_customers"
    )

    
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company, readonly=True)
    
    def set_all_slots_delivered(self:Type['Delivery']) -> None:
        for delivery in self:
            if delivery.status not in self.VALID_STATUSES_SLOT_STATUS_CHANGE:
                if delivery.slot_ids.filtered(lambda slot:slot.status == 'scheduled'):
                    delivery._set_slots_delivered(delivery)
                    body = f'All slots has been set to delivered by {self.env.user.name} on {datetime.datetime.now()}'
                    delivery.message_post(body=body)
                else:
                    raise UserError("No Scheduled Slots!")
            else:
                raise UserError("A delivery must be at least in transit if you want to deliver a slot!")

    def _set_slots_delivered(self:Type['Delivery'], delivery:Type['Delivery']) -> None:
        for slot in delivery.slot_ids:
            slot.set_delivered()


    def set_all_slots_cancelled(self:Type['Delivery']) -> None:
        for delivery in self:
            if delivery.status not in self.VALID_STATUSES_SLOT_STATUS_CHANGE:
                scheduled_slots = delivery.slot_ids.filtered(lambda slot:slot.status == 'scheduled')
                if scheduled_slots:
                    for slot in scheduled_slots:
                        delivery._set_slots_cancelled(delivery)
                        body = f'{scheduled_slots} has been set to Cancelled by {self.env.user.name} on {datetime.datetime.now()}'
                        delivery.message_post(body=body)
                else:
                    raise UserError("No Scheduled Slots!")
            else:
                raise UserError("A delivery must be at least in transit if you want to Cancel a slot!")

    def _set_slots_cancelled(self:Type['Delivery'], delivery:Type['Delivery']) -> None:
        for slot in delivery.slot_ids:
            slot.cancel_action()

    @api.constrains("sale_order_ids")
    def _compute_customers(self:Type['Delivery']) -> None:
        """Compute the list of customers for the delivery"""
        for delivery in self:
            # Get a list of customer names from the sale orders in the delivery
            customer_names = [sale_order.partner_id.name for sale_order in delivery.sale_order_ids]
            # Join the customer names into a single string with separator "-"
            customers_str = " - ".join(customer_names)
            # Set the customers field of the delivery to the generated string
            delivery.customers = customers_str if customer_names else ""


    @api.constrains("vehicle_id")
    def refresh_all_vehicles_assigned(self:Type['Delivery']) -> None:
        """
        Refreshes the 'all_vehicles_assigned' field on all sale orders
        associated with this delivery
        """
        for delivery in self:
            for order in delivery.sale_order_ids:
                order._compute_all_vehicles_assigned()


    def reallocate_to(self:Type['Delivery'], delivery_id:str) -> bool:
        for delivery in self:
            if delivery_id.status == "scheduled":
                for slot in delivery.slot_ids:
                    slot.change_delivery(
                        delivery_id, "Assignment", datetime.datetime.now())

                return True

    def return_reallocate_deliveries_view(self:Type['Delivery']) -> Dict:
        return {
            'name': 'reallocate Deliveries',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'logistic.delivery.reassignment',
            'target': 'new',
            'context': {
                "delivery_ids": self.env.context.get("active_ids"),
                "default_reallocated_volume": sum(self.env["logistic.delivery"].browse(self.env.context.get("active_ids")).mapped("total_volume")),
                "default_reallocated_assembly": sum(self.env["logistic.delivery"].browse(self.env.context.get("active_ids")).mapped("total_assembly")),
            }
        }

    

    @api.constrains('date')
    def _update_delivery_date_and_related_objects(self:Type['Delivery']) -> None:
        """
        Update the delivery date and related objects when the delivery date changes.

        This method is triggered when the 'date' field is updated on the delivery record. It ensures that the new date is not in
        the past and updates the delivery date and related objects (slots and status records) with the new date.

        Raises:
            UserError: If the new date is in the past.

        """
        # Iterate over each record that triggered the constraint (in this case, there should be only one)
        for delivery in self:
            # Check that the new date is not in the past
            if delivery.date_in_past():
                raise UserError("Delivery date cannot be in the past.")

            # Update the delivery date
            new_date = delivery.date

            # Update the date on all related slots and their corresponding sale orders
            for slot in delivery.slot_ids:
                slot.date = new_date
                slot.sale_order_id.delivery_date = new_date

                # Get or create a new status record for the slot and sale order with the updated date
                slot.get_or_create_status_record(slot, slot.sale_order_id)


    def date_in_past(self:Type['Delivery']) -> bool:
        for delivery in self:
            return True if delivery.date and delivery.date < datetime.datetime.today().date() else False
                
          

    @api.depends("slot_ids")
    def _compute_tech_ids(self:Type['Delivery']) -> None:
        for delivery in self:
            tech_ids = []
            if delivery.slot_ids:
                for slot in delivery.slot_ids:
                    for tech in slot.technician_ids:
                        if tech.id not in tech_ids:
                            tech_ids.append(tech.id)
                delivery.tech_ids = [(6, 0, tech_ids)]
            else:
                delivery.tech_ids = False

    def redirect_vehicle_kanban(self:Type['Delivery']) -> None:
        return {
            'name': 'Vehicle Kanban',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'kanban,tree,form',
            'res_model': 'fleet.vehicle',
            'target': 'current',
            'context': {
                    'default_delivery_id': self.id,
                    'default_date': self.date,
            }
        }

    @api.depends("slot_ids")
    def _compute_assembly_info_static(self:Type['Delivery']) -> None:
        for delivery in self:
            if delivery.slot_ids:
                delivery.left_side_panel_assembly_info_static = f'''
                <table class="table table-bordered" style='text-align:center;width=100%;margin:0;font-size:10px;'>
                    
                    <thead style='background-color:#714B67;color:white;'>
                        <tr>
                            <th>Delivery</th>
                            <th>hours</th>
                            <th>Zone</th>
                        </tr>
                    
                    </thead>
                    <tbody>
                        <tr>
                            <td>{delivery.name}</td>
                            <td>{delivery.total_assembly}</td>
                            <td>{delivery.zone_id.name}</td>
                        </tr>
                    </tbody>
                    
                </table>
                
                '''
            else:
                delivery.left_side_panel_assembly_info_static = f'''
                <table class="table table-bordered" style='text-align:center;width:100%;margin:0;font-size:10px;'>
                
                <thead style='background-color:#714B67;color:"white";'>
                    <tr>
                        <th style='background-color:#714B67;color:white;'>
                            {delivery.name if delivery.name else ""}
                        </th>
                    </tr>
                </thead>
                <tbody>
                        <tr style='background-color:#714B67;color:white;'>
                            <td>
                                <h5 style='color:white';>Empty Delivery</h5>
                            </td>
                        </tr>

                    </tr>
                </tbody>
            </table>'''

    @api.depends("slot_ids")
    def _compute_fsm_ids(self:Type['Delivery']) -> None:
        for delivery in self:
            fsm_ids = []
            if delivery.slot_ids:
                for slot in delivery.slot_ids:
                    if slot.fsm_id:
                        fsm_ids.append(slot.fsm_id.id)
                delivery.fsm_ids = [(6, 0, fsm_ids)]
            else:
                delivery.fsm_ids = False

    @api.depends("fsm_ids")
    def _compute_assembly_info(self:Type['Delivery']) -> None:
        for delivery in self:
            if delivery.fsm_ids:
                for task in delivery.fsm_ids:
                    if task.assembly_line_id:
                        bkg_colors = []
                        ids = []
                        rows = []
                        for line in task.assembly_line_id.order_id.order_line:
                            sol_task_id = task.id
                            ids.append(sol_task_id)
                            rows.append([line.product_id.name, line.product_id.assembly_time,
                                        task.effective_hours, " - ".join([user.name for user in task.user_ids])])
                            bkg_colors.append(
                                "#aaaaaa" if line == task.assembly_line_id else "#ffffff")
                        rows.append([
                            "Total",
                            sum([
                                line.product_id.assembly_time for line in task.assembly_line_id.order_id.order_line]),
                            sum(self.env["project.task"].search(
                                [("assembly_sale_order_id", "=", task.assembly_line_id.order_id.id)]).mapped("effective_hours")),
                            ' '
                        ]

                        )
                        ids.append(-1)
                        delivery.left_side_panel_assembly_info = self.form_table_fsm(
                            headers=["Product", "Time/P", "Task time", "Tech"],
                            rows=rows,
                            ids=ids,
                            name=task.assembly_line_id.order_id.name,
                            stage=task.stage_id.name,
                            bkg_colors=bkg_colors,

                        )

            else:
                delivery.left_side_panel_assembly_info = ""

    @api.depends("slot_ids")
    def _compute_total_assembly(self:Type['Delivery']) -> None:
        for record in self:
            total_assembly = 0
            for slot in record.slot_ids:
                total_assembly += slot.assembly_time
            record.total_assembly = total_assembly

    #TODO:Create a Colors model and link them to states
    @api.depends('status')
    def _compute_color(self:Type['Delivery']) -> None:
        """Computes color depending on active or not, red for inactive and green for active"""
        for cluster in self:
            if cluster.status == "cancelled":
                cluster.color = 1
            if cluster.status == "scheduled":
                cluster.color = 3
            if cluster.status == "loaded":
                cluster.color = 6
            if cluster.status == "in_transit":
                cluster.color = 8
            if cluster.status == "fulfilled":
                cluster.color = 10

    def form_table_fsm(self:Type['Delivery'], headers:list, rows:list, ids:list[int], name:str = None, background_color:str = "#714B67", color: str = "white", stage: str = None, bkg_colors: str =None) -> str:
        

        """
        generates an HTML table with the provided data and styling options. The table includes a header row, column headers, and a body with multiple rows.

        Parameters:

        rows (list): A list of dictionaries representing the data for each row in the table.
        headers (list): A list of strings representing the column headers for the table.
        background_color (str): The background color of the table header.
        color (str): The text color of the table header.
        name (str, optional): The name displayed in the top header cell. If not provided, the cell will be empty.
        bkg_colors (list, optional): A list of background colors for each row. If not provided, all rows will have a white background color.
        ids (list, optional): A list of IDs for each row. These IDs are used for additional processing in the self.form_row_fsm() method.
        Returns:

        html (str): A string containing the HTML code for the generated table with the specified data and styling.
        
        """
        
        bkg_colors = [
            "#ffffff" for item in rows] if not bkg_colors else bkg_colors
        while len(bkg_colors) < len(rows):
            bkg_colors.append("#ffffff")

        return f'''
            <table class="table table-bordered" style='text-align:center;width:280px;margin:0;font-size:10px;'>
                
                <thead style='background-color:{background_color};color:{color};'>
                    <tr>
                        <th colspan="{len(headers)}" style='background-color:{background_color};color:{color};'>
                            {name if name else ""}
                        </th>
                    </tr>
                    <tr>
                        {" ".join([f"<th>{th}</th>" for th in headers])}
                    </tr>
                   
                </thead>
                <tbody>
                    {" ".join([self.form_row_fsm(row,bkg_colors[index], ids[index]) for index,row in enumerate(rows)])}
                </tbody>
                
            </table>
            <img src="/logistic_automation/static/src/img/{stage}.png" style='width:40px;height:40px;'>
        '''

    def form_row_fsm(self:Type['Delivery'], cells:list, color:str, id:int) -> str:
        return f'''
            <tr {f"class='tr' id='{id}'"} style='background-color:{color};'>
                {" ".join([f"<td>{cell}</td>" for cell in cells])}
            </tr>
        '''

    def _compute_sale_orders_count(self:Type['Delivery']) -> None:
        for delivery in self:
            delivery.sale_orders_count = len(delivery.sale_order_ids)

    def _compute_task_count(self:Type['Delivery']) -> None:
        for delivery in self:
            delivery.task_count = len(delivery.slot_ids.mapped("fsm_id"))

    def _compute_side_button_info(self:Type['Delivery']) -> None:
        for delivery in self:
            if delivery.slot_ids:
                delivery.side_button_info = self.form_table(
                    ["Empty", "Zone", "CBM", "Remaining", "Total S.O"],
                    [[delivery.vehicle_id.total_capacity if delivery.vehicle_id else "N/A", delivery.zone_id.name,
                        delivery.total_volume, delivery.remaining_volume, len(delivery.sale_order_ids)]],
                    delivery.name,
                    background_color="#714B67",
                    color="white",
                    width="100%")
            else:
                delivery.side_button_info = f'''
            <table class="table table-bordered" style='text-align:center;width:100%;margin:0;font-size:10px;'>
                
                <thead style='background-color:#714B67;color:"white";'>
                    <tr>
                        <th style='background-color:#714B67;color:white;'>
                            {delivery.name if delivery.name else ""}
                        </th>
                    </tr>
                </thead>
                <tbody>
                        <tr style='background-color:#714B67;color:white;'>
                            <td>
                                <h5 style='color:white';>Empty Delivery</h5>
                            </td>
                        </tr>

                    </tr>
                </tbody>
            </table>
        '''

    def reset_to_scheduled(self:Type['Delivery']) -> None:
        for delivery in self:
            slots = delivery.slot_ids.filtered(
                lambda slot: slot.status == "delivered" or slot.status == "returned")
            if slots:
                raise UserError(
                    "Cannot reset to scheduled because there are slots in that are delivered/returned status")
            else:
                for slot in delivery.slot_ids:
                    slot.status = "scheduled"
                delivery.status = "scheduled"
                # for order in self.sale_order_ids:
                #     order._compute_all_deliveries_fulfilled()

    def unlink(self:Type['Delivery']) -> bool:
        for delivery in self:
            if delivery.status != "cancelled":
                raise UserError("You can only delete cancelled deliveries")
        for item in delivery.slot_ids:
            item.unlink()
        return super(Delivery, self).unlink()

    def _compute_district_ids(self:Type['Delivery']) -> None:
        for delivery in self:
            if delivery.slot_ids:
                delivery.district_ids = list(
                    set(delivery.slot_ids.mapped("district_id")))
            else:
                delivery.district_ids = False

    # populates a vehicle slot ids with a delivery slots when a vehicle is assigned to the delivery

    @api.constrains("vehicle_id")
    def assign_slots_vehicle(self:Type['Delivery']) -> None:
        for delivery in self:
            if delivery.vehicle_id:
                for slot in delivery.slot_ids:
                    slot.vehicle_id = delivery.vehicle_id

    @api.depends('slot_ids')
    def _compute_all_techs_assigned(self:Type['Delivery']) -> None:
        # Iterate through each delivery
        for delivery in self:
            # Check if all technicians have been assigned to the delivery
            if delivery.ensure_tech_assigned():
                delivery.all_techs_assigned = True
            else:
                delivery.all_techs_assigned = False


    def form_table(self, headers:list, rows:list, name: str = None, background_color: str = "#714B67", color:str = "white", width:str = "280px") -> str:
        return f'''
            <table class="table table-bordered" style='text-align:center;width:{width};margin:0;font-size:10px;'>
                
                <thead style='background-color:{background_color};color:{color};'>
                    <tr>
                        <th colspan="{len(headers)}" style='background-color:{background_color};color:{color};'>
                            {name if name else ""}
                        </th>
                    </tr>
                    <tr>
                        {" ".join([f"<th>{th}</th>" for th in headers])}
                    </tr>
                   
                </thead>
                <tbody>
                    {" ".join([self.form_row(row) for row in rows])}
                </tbody>
            </table>
        '''

    def form_row(self:Type['Delivery'], cells:list) -> str:
        return f'''
            <tr>
                {" ".join([f"<td>{round(cell,2) if type(cell) is float else cell}</td>" for cell in cells])}
            </tr>
           
        '''

    def _compute_info(self:Type['Delivery']) -> None:
        """Perpares information for the info field, those info will be displayed in the map view"""
        for delivery in self:
            section_1 = '''
            <b>Vehicle:</b> {}<br>
            <b>Total Vehicle Space:</b> {}<br>
            <b>Status:</b> {}<br>
            <b>Progress:</b> {}<br>
            <b>Cluster:</b> {}<br>
            <b>Zones:</b> {}<br>
            '''.format(delivery.vehicle_id.name if delivery.vehicle_id else "Not assigned yet!", delivery.vehicle_id.total_capacity if delivery.vehicle_id else "Not assigned yet!", delivery.status, delivery.progress, delivery.cluster_id.name, " - ".join([zone.name for zone in delivery.slot_ids.mapped("zone_id")]))
            tables = ""
            for order in delivery.sale_order_ids:
                line_items = []
                for line in order.order_line:
                    line_items.append(
                        [line.product_id.name, line.product_id.assembly_time, line.volume])
                line_items.append(
                    ["Total", order.order_assembly_time, order.total_order_volume])
                table = self.form_table(
                    ["Product", "Time", "CBM"], line_items, line.order_id.name)
                tables += table
            delivery.info = section_1 + tables

    def assign_technicians(self:Type['Delivery'], values:list[int]) -> None:
        for item in values:
            delivery_id = self.env["logistic.delivery"].search(
                [("id", "=", item.get('delivery_id'))])
            if delivery_id:
                line_ids = delivery_id.slot_ids.filtered(
                    lambda x: x.sale_order_id.id == item.get('order_id'))
                if line_ids:
                    for line in line_ids:
                        try:
                            line_ids.technician_ids = item.get(
                                'technician_ids')
                        except Exception as e:
                            raise UserError(e)
                else:
                    raise UserError(
                        "No slot found for order {}".format(item.get('order_id')))
            else:
                raise UserError(
                    "No delivery found for order {}".format(item.get('order_id')))

    @api.depends('slot_ids')
    def _compute_zone_id(self:Type['Delivery']) -> None:
        for delivery in self:

            zone_ids = list(delivery.slot_ids.mapped("zone_id"))
            if zone_ids:
                if zone_ids.count(zone_ids[0]) == len(zone_ids):
                    delivery.zone_id = zone_ids[0]
                    delivery.mismatched_zones = False
                else:
                    delivery.zone_id = False
                    delivery.mismatched_zones = True
            else:
                delivery.zone_id = False
                delivery.mismatched_zones = False

    @api.depends('sale_order_ids')
    def _compute_delivery_count(self:Type['Delivery']) -> None:
        for delivery in self:
            if delivery.sale_order_ids:
                delivery.delivery_count = len(delivery.sale_order_ids)
            else:
                delivery.delivery_count = 0

    def action_view_delivery(self:Type['Delivery']) -> Dict:
        form_view_id = self.env.ref('stock.view_picking_form').id
        tree_view_id = self.env.ref('stock.vpicktree').id

        return {
            'name': 'Delivery',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'stock.picking',
            'domain': [('sale_id', 'in', self.sale_order_ids.ids)],
            'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
            'view_id': tree_view_id,
            'target': 'current',

        }

    @api.depends('slot_ids')
    def _compute_sale_order_ids(self:Type['Delivery']) -> None:
        for delivery in self:
            if delivery.slot_ids:
                delivery.sale_order_ids = delivery.slot_ids.mapped(
                    'sale_order_id').ids
            else:
                delivery.sale_order_ids = False

    @api.depends('slot_ids', 'vehicle_id')
    def _compute_volume_loss_percentage(self:Type['Delivery']) -> None:
        for delivery in self:
            if delivery.vehicle_id and delivery.vehicle_id.total_capacity > 0 and delivery.total_volume:
                delivery.volume_loss_percentage = delivery.volume_loss / \
                    delivery.vehicle_id.total_capacity * 100
            else:
                delivery.volume_loss_percentage = 0

    def ensure_fits(self:Type['Delivery']) -> None:
        for delivery in self:
            if delivery.vehicle_id:
                if delivery.total_volume > delivery.vehicle_id.total_capacity:
                    return False
                else:
                    return True
            else:
                return True

    @api.onchange("vehicle_id")
    def onchange_vehicle_id(self:Type['Delivery']) -> None:
        """invokes ensure_fits, which makes sure the products fits in the vehicle"""
        if not self.ensure_fits():
            raise UserError("Vehicle capacity is not enough for this delivery")
        else:
            pass

    @api.depends('delivered_volume', 'total_volume')
    def _compute_progress(self:Type['Delivery']) -> None:
        for delivery in self:
            if delivery.total_volume:
                delivery.progress = delivery.delivered_volume / delivery.total_volume * 100
            else:
                delivery.progress = 0

    @api.depends('slot_ids')
    def _compute_volume_loss(self:Type['Delivery']) -> None:
        for delivery in self:
            if delivery.vehicle_id and delivery.slot_ids:
                total_vehicle_volume = delivery.vehicle_id.total_capacity
                total_slots_volume = sum(
                    delivery.slot_ids.mapped('total_volume'))
                delivery.volume_loss = total_vehicle_volume - total_slots_volume
            else:
                # Was = 0, caused an issue when an empty delivery has no lines, amounts to zero while it should be vehicle total.
                delivery.volume_loss = delivery.vehicle_id.total_capacity

    def _compute_trip_duration(self:Type['Delivery']) -> None:
        for delivery in self:
            if delivery.trip_start_time and delivery.trip_end_time:
                delivery.trip_duration = (
                    delivery.trip_end_time - delivery.trip_start_time).total_seconds() / 3600
            elif delivery.trip_start_time and not delivery.trip_end_time:
                delivery.trip_duration = (datetime.datetime.now(
                ) - delivery.trip_start_time).total_seconds() / 3600
            else:
                delivery.trip_duration = 0

    @api.depends('slot_ids')
    def _compute_total_volume(self:Type['Delivery']) -> None:
        for record in self:
            record.total_volume = sum(
                slot.total_volume for slot in record.slot_ids if slot.status != "cancelled")

    @api.depends("slot_ids")
    def _compute_delivered_volume(self:Type['Delivery']) -> None:
        for record in self:
            record.delivered_volume = sum(
                slot.total_volume for slot in record.slot_ids if slot.is_delivered)

    @api.depends("delivered_volume", "total_volume")
    def _compute_remaining_volume(self:Type['Delivery']) -> None:
        for record in self:
            record.remaining_volume = record.total_volume - record.delivered_volume

    

    @api.model
    def create(self:Type['Delivery'], values:Union[list[Dict], Dict]) -> Union(list[Type['Delivery']],Type['Delivery']):
        """Generate a uuid on each creation, assign delivery sequence"""
        if isinstance(values, list):
            for val in values:
                val['guid'] = uuid.uuid4()
        elif isinstance(values, dict):
            values['guid'] = uuid.uuid4()
        values['name'] = self.env['ir.sequence'].next_by_code(
            'logistic.delivery.code')
        result = super(Delivery, self).create(values)
        return result

    def set_loaded(self:Type['Delivery']) -> None:
        for delivery in self:
            if not delivery.vehicle_id:
                raise UserError("Please select vehicle")
            for sale_order in delivery.sale_order_ids:
                for picking in sale_order.picking_ids.filtered(lambda picking: picking.location_dest_id.usage == "transit"):
                    if picking.state != "done":
                        raise UserError(
                            "Please validate  all the transfers with destination 'Transit' before setting the delivery as loaded")
        self.status = "loaded"

    

    def start_trip(self:Type['Delivery']) -> None:
        self.status = "in_transit"
        self.trip_start_time = datetime.datetime.now()
        self.vehicle_id.is_en_route = True

    def end_trip(self:Type['Delivery']) -> None:
        no_status_update = self.ensure_slot_status_update()
        if no_status_update:
            raise UserError(
                "The following Slots has no status update: %s" % str(no_status_update))
        self.trip_end_time = datetime.datetime.now()
        self.vehicle_id.is_en_route = False

    def ensure_slot_status_update(self:Type['Delivery']) -> Union(list[str], list):
        result = []
        for slot in self.slot_ids:
            if not slot.is_delivered and not slot.is_returned:
                result.append(slot.name)
        return result

    def set_fulfilled(self:Type['Delivery']) -> None:
        self.status = "fulfilled"
        self.fullfilled_date = fields.Datetime.now()
        self._check_sale_orders_fulfilled(self) 

    def _check_sale_orders_fulfilled(self:Type['Delivery'], obj:Type['Delivery']) -> None:
        for order in obj.sale_order_ids:
            if self._is_sale_order_fulfilled(order):
                order.check_all_deliveries_fulfilled()

    def _is_sale_order_fulfilled(self:Type['Delivery'], order:Type['SaleOrder']) -> bool:
        for picking in order.picking_ids.filtered(lambda picking: picking.location_dest_id.usage == "customer"):
            if picking.state != "done":
                return False
        return len(order.logistic_delivery_ids.filtered(lambda d: not d.status == 'delivered')) == 0


    def ensure_tech_assigned(self:Type['Delivery']) -> bool:
        result = []
        for slot in self.slot_ids:
            if slot.sale_order_line_id.product_id.require_assembly:
                if not slot.technician_ids:
                    result.append(slot.name)
        return False if result else True

    def cancel_action(self:Type['Delivery']) -> None:
        for delivery in self:
            if delivery.status in ["in_transit", "loaded"]:
                for order in delivery.sale_order_ids:
                    validated_pickings_vehicle = order.picking_ids.filtered(
                        lambda picking: picking.state == "done" and picking.location_dest_id.usage == 'transit')
                    validated_pickings_customer = order.picking_ids.filtered(
                        lambda picking: picking.state == "done" and picking.location_dest_id.usage == 'customer')
                    if validated_pickings_vehicle or validated_pickings_customer:
                        raise UserError(
                            "Please reverse all validated  transfers cancel this delivery")
            if delivery.status == "fulfilled":
                raise UserError(
                    "You can only cancel a delivery that is not yet fulfilled")
            for slot in delivery.slot_ids:
                slot.cancel_action()
            self.status = "cancelled"
            self.cancelled_date = fields.Datetime.now()

    def action_view_tasks(self:Type['Delivery']) -> Dict:
        return {
            'name': 'Tasks',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'project.task',
            'domain': [('delivery_id', '=', self.id)],
        }

    def action_view_orders(self:Type['Delivery']) -> Dict:
        return {
            'name': 'Sale Orders',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'sale.order',
            'domain': [('id', '=', self.sale_order_ids.ids)],
        }

    def action_view_items(self:Type['Delivery']) -> Dict:

        return {
            'name': 'Sales Order Items',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'sale.order.line',
            'target': 'new',
            'domain': [('order_id', 'in', self.sale_order_ids.ids)],
            'context': "{'group_by':'order_id'}"
        }


# A transient model to filter deliveries using a calendar
class DeliveryDatePicker(models.TransientModel):
    _name = "delivery.date.picker"


    date = fields.Date(string="Select Date", default=fields.Date.today)

    def action_submit(self:Type['Delivery']) -> Dict:
        return {
            'name': 'Deliveries',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'res_model': 'logistic.delivery',
            'domain': [('date', '=', self.date)],
        }
