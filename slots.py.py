# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import datetime
from os import urandom
import hashlib
import uuid


class Slot(models.Model):

    """ Part of the delivery vehicle that holds an order line item """

    _name = "logistic.slot"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Slot"
    _rec_name = 'name'

    STATUS = [('scheduled', 'Scheduled'),
              ('delivered', 'Delivered'),
              ('returned', 'Returned'),
              ('cancelled', 'Cancelled')]

    guid = fields.Char(
        "GUID",
        readonly=True,
        copy=False,
        index=True
    )

    customer_floor = fields.Integer(
        string="Floors",
        related = "customer_id.floors",)

    name = fields.Char(
        string="Name",
        readonly=True,
        copy=False,
        index=True
    )

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        related="sale_order_line_id.product_id",
        readonly=True,
        store=True
    )

    description = fields.Text(
        string="Description",
        track_visibility='onchange'
    )

    customer_id = fields.Many2one(
        "res.partner",
        related="sale_order_id.partner_id",
        string="Customer",
        store=True,
        track_visibility='onchange'
    )

    date = fields.Date(
        string="Slot Date",
        track_visibility='onchange',

    )

    delivery_id = fields.Many2one(
        "logistic.delivery",
        string="Delivery",
        track_visibility='onchange'
    )

    vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Vehicle",
        track_visibility='onchange'
    )

    sale_order_id = fields.Many2one(
        related="sale_order_line_id.order_id",
        string="Order",
        store=True,
        track_visibility='onchange'
    )
    sale_order_line_id = fields.Many2one(
        "sale.order.line",
        string="Sale Order Line",
        track_visibility='onchange'
    )

    assembly_time = fields.Float(
        string="Assembly Time",
        related="sale_order_line_id.product_id.assembly_time",
    )

    total_volume = fields.Float(
        string="Total Volume",
        related="sale_order_line_id.volume"
    )
    date_delivered = fields.Datetime(
        string="Date Delivered",
        track_visibility='onchange'
    )
    is_delivered = fields.Boolean(
        string="Is Delivered",
        track_visibility='onchange'
    )
    is_returned = fields.Boolean(
        string="Is Returned",
        track_visibility='onchange'
    )
    picking_id = fields.Many2one(
        "stock.picking",
        string="Picking"
    )

    zone_id = fields.Many2one(
        "logistic.zone", string="Zone",
        related="sale_order_id.zone_id",
        store=True,

    )

    cluster_id = fields.Many2one(
        "logistic.cluster",
        string="Cluster",
        related="sale_order_id.cluster_id",
        store=True

    )

    district_id = fields.Many2one(
        "logistic.district",
        string="District",
        related="sale_order_id.district_id",
        store=True
    )

    assembly_time = fields.Float(
        string="Total Assembly",
        compute="_compute_total_assembly_time",

    )

    technician_ids = fields.Many2many(
        "technician.technician",
        string="Technicians",
        track_visibility='onchange'

    )

    status = fields.Selection(
        STATUS,
        string="Status",
        default="scheduled",
        track_visibility='onchange'
    )

    all_day = fields.Boolean(
        string="All Day",
        default=True
    )

    zone_status_id = fields.Many2one(
        "logistic.zone.status",
        string="Zone Status"
    )

    fsm_id = fields.Many2one(
        comodel_name="project.task",
        string="Tasks",
        track_visibility='onchange'
    )

    active = fields.Boolean(
        string="Active",
        default=True,
        track_visibility='onchange'
    )

    lon = fields.Float(
        string="Longitude",
        compute="compute_lon",
        digits=(16, 10)

    )
    lat = fields.Float(
        string="Latitude",
        compute="compute_lat",
        digits=(16, 10)

    )

    assembly_planned_date_begin = fields.Datetime(
        string="Assembly Planned Date Begin",
        default=lambda slot: slot.date_delivered if slot.date_delivered else False
    )

    assembly_planned_date_end = fields.Datetime(
        string="Assembly Planned Date End",
        default=lambda slot: slot.assembly_planned_date_begin +
        datetime.timedelta(
            hours=slot.assembly_time) if slot.assembly_planned_date_begin else False
    )

    return_justification = fields.Many2one(
        "justification.justification",
        string="Return Justification",
        track_visibility='onchange'
    )

    def return_create_task_view(self):

        fsm_project_id = self.env["project.project"].search(
            [("is_fsm", "=", True)])[0]
        if fsm_project_id:
            """ returns the view of the return wizard"""
            return {
                'name': 'Return',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'project.task',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'context': {
                    'default_name': self.name,
                    'default_project_id': fsm_project_id.id,
                    'default_assembly_line_id': self.sale_order_line_id.id,
                    'default_user_ids': [(6, 0, self.technician_ids.ids)],
                    'default_planned_date_begin': self.date_delivered,
                    'default_partner_id': self.sale_order_id.partner_id.id,
                    'default_description': self.description,
                    'default_slot_id': self.id,
                    'redirect': True

                }
            }

        else:
            raise UserError("Please create a FSM project")

    def _compute_total_assembly_time(self):
        for slot in self:
            slot.assembly_time = slot.sale_order_line_id.product_id.assembly_time * \
                slot.sale_order_line_id.product_uom_qty

    def compute_lon(self):
        for slot in self:
            if slot.sale_order_line_id.order_id.partner_id.partner_longitude:
                slot.lon = slot.sale_order_line_id.order_id.partner_id.partner_longitude
            else:
                slot.lon = slot.zone_id.center_lon

    def compute_lat(self):
        for slot in self:
            if slot.sale_order_line_id.order_id.partner_id.partner_latitude:
                slot.lat = slot.sale_order_line_id.order_id.partner_id.partner_latitude
            else:
                slot.lat = slot.zone_id.center_lat

    def view_change_delivery_wizard(self):
        """ returns the view of the change delivery wizard"""
        return {
            'name': 'Change Delivery',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'logistic.slot.delivery.change',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {
                'default_slot_ids': [slot.id for slot in self],
                # 'default_delivery_id': self.delivery_id.id,
            }
        }

   

    def change_delivery(self, delivery_id, reason, date):
        """Changes the delivery ID if compatible with the delivery."""
        if not self.check_compatible(delivery_id):
            raise UserError("The target delivery is not in scheduled state or the vehicle does not have the capacity to carry the product")

        old_delivery_id = self.delivery_id
        self.delivery_id = delivery_id
        self.sale_order_id._compute_logistic_delivery_ids()

        body = f"Slot transferred from {old_delivery_id.name} to {delivery_id.name} at {date} by {self.env.user.name} for the reason {reason}"
        self.message_post(body=body)

        return True


    def check_compatible(self, delivery_id):
        """ Check if the slot is compatible with the delivery by checking that they have same cluster and date and the target delivery is scheduled not in transit or delivered"""
        if delivery_id.vehicle_id:
            if delivery_id.status == "scheduled":
                if delivery_id.volume_loss > self.total_volume:
                    return True
                else:
                    return False
            else:
                raise UserError("Target delivery is not in scheduled status!")
        else:
            raise UserError("Please Assign a vehicle to target delivery!")

    def cancel_action(self):
        for slot in self:
            if slot.status in ["delivered", "returned"]:
                raise UserError(
                    "Cannot cancel a slot that is delivered or returned")
            else:
                slot.status = 'cancelled'  # sets slot as cancelled
                if slot.fsm_id:  # cancels related fsm
                    slot.fsm_id = self.env["project.task.type"].search(
                        [("name", "=", "Cancelled"), ("project_ids", "in", slot.fsm_id.project_id.id)], limit=1).id

    def schedule(self, order):
        try:
            delivery_id = self.create_delivery(order)
            slot_ids = self.create_slots(order, delivery_id.date)
            self.assign_slot_delivery(delivery_id, slot_ids)
            return True
        except Exception as e:
            return e

    # Returns vehicles available for order using order date and order total volume
    def get_vehicles(self, order):
        vehicles = self.env["fleet.vehicle"].get_available_vehicles(order)
        return vehicles

    def create_slots(self, order, date):
        slot_ids = []
        for line in order.order_line:
            try:
                slot_id = self.create({"description": line.product_id.name,
                                       "sale_order_line_id": line.id,
                                       "assembly_planned_date_begin": line.order_id.installation_date,
                                       "date": date, })

                self.get_or_create_status_record(slot_id, order)
                slot_ids.append(slot_id)
            except Exception as e:
                return str(e)
        return slot_ids

   
    def get_or_create_status_record(self, slot_id, order):
        """
        Get or create the logistic zone status record for the given slot and order's zone.

        :param slot_id: the ID of the logistic slot to use
        :type slot_id: int
        :param order: the order object to use to get the zone
        :type order: logistic.order
        :return: True
        """
        # Search for an existing logistic zone status record for the given zone and slot date
        zone_status_id = self.env["logistic.zone.status"].search(
            [("zone_id", "=", order.zone_id.id), ("date", "=", slot_id.date)])

        # If no existing record is found, create a new one
        if not zone_status_id:
            zone_status_id = self.env["logistic.zone.status"].create({
                "zone_id": order.zone_id.id,
                "date": slot_id.date,
                "slot_ids": [(4, slot_id.id)]
            })
        # If an existing record is found, add the slot to its list of slots
        else:
            zone_status_id.slot_ids += slot_id
        # Return True to indicate that the method executed successfully
        return True


    # Assigns slots to vehicle
    def assign_slot_to_vehicle(self, vehicle_id, slot_ids):
        for slot_id in slot_ids:
            vehicle_id.slot_ids += slot_id
            slot_id.write({"vehicle_id": vehicle_id.id})
        return True

    # Creates a delivery for the order
    def create_delivery(self, order):
        try:
            delivery_id = self.env["logistic.delivery"].create({
                "date": order.delivery_date,
            })

            return delivery_id
        except Exception as e:
            return str(e)

    # Assigns the delivery to the slots
    def assign_slot_delivery(self, delivery_id, slot_ids):
        for slot_id in slot_ids:
            slot_id.write({"delivery_id": delivery_id.id})
            delivery_id.slot_ids += slot_id
        return True

    # Update delivery record to mark as delivered and set delivered date
    def set_delivered(self):
        self.is_delivered = True
        self.status = 'delivered'
        self.date_delivered = fields.Datetime.now()
        #15/6/2023-Removed due to the removing of adding tech to slot restriction, will revise later.
        # Create FSM task if product requires assembly and a corresponding FSM project exists
        # fsm_project = self.env["project.project"].search([("is_fsm", "=", True)], limit=1)
        # if fsm_project:
        #     if self.sale_order_line_id.product_id.require_assembly:
        #         try:
        #             fsm_task_vals = {
        #                 "name": self.name,
        #                 "project_id": fsm_project.id,
        #                 "assembly_line_id": self.sale_order_line_id.id,
        #                 "user_ids": self.technician_ids.ids,
        #                 "planned_date_begin": self.assembly_planned_date_begin,
        #                 "planned_date_end": self.assembly_planned_date_end,
        #                 "partner_id": self.sale_order_id.partner_id.id,
        #                 "description": self.description,
        #                 "slot_id": self.id
        #             }
        #             fsm_task = self.env["project.task"].create(fsm_task_vals)
        #             self.fsm_id = fsm_task.id
        #         except Exception as e:
        #             raise UserError(_("Failed to create FSM task: %s" % str(e)))
        # else:
        #     raise UserError(_("No FSM project found."))
        
    def set_returned_driver_portal(self):
        self.is_returned = True
        self.status = 'returned'
        self.message_post(body=f"Slot returned by {self.env.user.name} at {datetime.datetime.now()}")

    def return_assign_technicians_view(self):

        return {
            'name': 'Assign Technincians Technicians',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'logistic.slot.tech.assignment',
            'target': 'new',
            'context': {
                "slot_ids": self.env.context.get("active_ids"),
            }
        }

    def set_returned(self):
        return {
            'name': 'Reason for Return',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'return.product.justification',
            'target': 'new',
            'context': {
                "slot_id": self.id,
            }
        }

    def unlink(self):
        for slot in self:
            if slot.status != "cancelled":
                raise UserError(
                    "Cannot delete a slot that is not in Canclled state")
            else:
                super(Slot, self).unlink()
        return True

    def reset_to_scheduled(self):
        for slot in self:
            if slot.delivery_id:
                if slot.delivery_id.status != "scheduled":
                    raise UserError(
                        f"Please reset the delivery {slot.delivery_id.name} to scheduled status before resetting the slot")
        slot.status = 'scheduled'

    @api.model
    def create(self, values):
        if isinstance(values, dict):
            values['name'] = self.env['ir.sequence'].next_by_code(
                'logistic.slot.code')
            values['guid'] = uuid.uuid4()
        elif isinstance(values, list):
            for value in values:
                value['name'] = self.env['ir.sequence'].next_by_code(
                    'logistic.slot.code')
                value['guid'] = uuid.uuid4()
        res = super(Slot, self).create(values)
        return res