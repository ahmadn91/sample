# -*- coding: utf-8 -*-


"""

The provided code is a Python script that defines two Odoo models: Cluster and LogisticZoneDateStatus. These models are used in the Odoo framework to manage logistics clusters and zone statuses.

The Cluster model represents a logistics cluster that can contain one or more logistics zones. It has fields such as name, description, is_active, zone_ids, slot_ids, total_slots, and various computed fields that calculate statistics related to the cluster.

The LogisticZoneDateStatus model represents the status of a logistics zone for a specific date. It has fields such as summary, date, zone_id, slot_ids, total_volume, and computed fields that calculate statistics related to the zone status.

Both models have various methods that perform calculations, handle redirects to related models, and provide other functionalities within the Odoo framework.

Please note that this code is meant to be used within an Odoo environment, and it relies on the Odoo framework and its ORM (Object-Relational Mapping) system to function properly.

"""
from os import urandom
import hashlib
import uuid
from xmlrpc.client import boolean
from odoo import models, fields, api, _, http
from datetime import datetime, timedelta
from odoo.exceptions import UserError
from typing import Union, List, Dict, Type
import json


TODAY = datetime.today()


class Cluster(models.Model):
    """
    The Cluster model class represents a logistics cluster that can contain one or more logistics zones.
    """
    _name = 'logistic.cluster'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Cluster'
    _order = 'name'
    _rec_name = 'name'

    guid = fields.Char(
        string="GUID",
        readonly=True,
        index=True
    )

    name = fields.Char(
        string='Name',
        required=True,
        translate=True,
        copy=False,
        track_visibility='onchange',
    )

    description = fields.Text(
        string='Description',
        track_visibility='onchange',
        copy=False,
    )

    is_active = fields.Boolean(
        string='Active',
        default=False,
        track_visibility='onchange',
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.user.company_id.id,
        readonly=True,
    )

    zone_ids = fields.One2many(
        "logistic.zone",
        "cluster_id",
        readonly=True,
        string="Zones",
        copy=False
    )

    slot_ids = fields.One2many(
        "logistic.slot",
        "cluster_id",
        string="Slots",
        copy=False
    )

    number_of_zones = fields.Integer(
        string="Number of zones",
        compute="_compute_number_of_zones",
    )

    total_slots = fields.Integer(
        string="Total slots",
        compute="_compute_total_slots"
    )

    total_delivered_slots = fields.Integer(
        string="Total delivered slots",
        compute="_compute_total_delivered_slots"
    )

    total_returned_slots = fields.Integer(
        string="Total returned slots",
        compute="_compute_total_returned_slots"
    )

    total_deliveries = fields.Integer(
        string="Total deliveries",
        compute="_compute_total_deliveries"
    )

    total_customers = fields.Integer(
        string="Total Customers",
        compute="_compute_total_customers",
        help="Total number of customers in the cluster"

    )

    reserved_volume_today = fields.Float(
        string="Reserved volume today",
        compute="_compute_reserved_volume_today"
    )

    center_lon = fields.Float(
        string="Cluster center longitude",
        compute="_compute_cluster_center",
        digits=(16, 10)
    )

    center_lat = fields.Float(
        string="Cluster center latitude",
        compute="_compute_cluster_center",
        digits=(16, 10)
    )

    color = fields.Integer(
        string="Color",
        compute="_compute_color",
    )

    @api.model
    def create(self:Type['Cluster'] , values: dict) -> Union[Type['Cluster'], List[Type['Cluster']]]:
        """Overrides create to accomodate guid generation

        Args:
        values (dict or list): A dictionary or a list of dictionaries containing 
            the field values for creating the record(s).

        Returns:
            object: A newly created LogisticCluster object.

        Raises:
            ValueError: If the provided values parameter is neither a dictionary nor a list.
        """
        if isinstance(values, list):
            for val in values:
                val['guid'] = uuid.uuid4()
        elif isinstance(values, dict):
            values['guid'] = uuid.uuid4()
        else:
            raise ValueError(
                'Invalid values parameter. Must be a dictionary or a list of dictionaries.')
        result = super(Cluster, self).create(values)
        return result

    @api.depends('is_active')
    def _compute_color(self:Type['Cluster']) -> None:
        """Computes color depending on active or not, red for inactive and green for active
        If `is_active` is True, sets the `color` field to 7 (green).
        If `is_active` is False, sets the `color` field to 1 (red).
        This method is automatically called whenever the value of `is_active` changes.
        Args:
        self (RecordSet): A set of `LogisticCluster` records.
        Returns:
        None.
        """
        for cluster in self:
            if cluster.is_active:
                cluster.color = 7
            else:
                cluster.color = 1

    def _compute_total_customers(self:Type['Cluster']) -> None:
        """
        Computes the total number of customers associated with a `LogisticCluster` record.
        Searches the `res.partner` model for all partners that have a `cluster_id` field that matches the `id` of the `LogisticCluster` record.
        Sets the `total_customers` field of the record to the count of the search result.
        This method is automatically called whenever the `id` field of a `LogisticCluster` record changes.
        Args:
            self (RecordSet): A set of `LogisticCluster` records.
        Returns:
        None."""
        for cluster in self:
            cluster.total_customers = self.env["res.partner"].search_count(
                [("cluster_id", "=", cluster.id)])

    def _compute_total_deliveries(self:Type['Cluster']) -> None:
        """Computes the total number of deliveries associated with a `LogisticCluster` record.
            Searches the `logistic.delivery` model for all deliveries that have a `cluster_id` field that matches the `id` of the `LogisticCluster` record.
            Sets the `total_deliveries` field of the record to the count of the search result.
            This method is automatically called whenever the `id` field of a `LogisticCluster` record changes.
            Args:
                self (RecordSet): A set of `LogisticCluster` records.

            Returns:
                None.
            """
        for cluster in self:
            cluster.total_deliveries = self.env["logistic.delivery"].search_count(
                [("cluster_id", "=", cluster.id)])

    @api.onchange('zone_ids')
    def _compute_cluster_center(self:Type['Cluster']) -> None:
        """Calculates the center longitude and latitude of a `LogisticCluster` record based on the center longitude and latitude of its associated `LogisticZone` records.
        This method is automatically called whenever the `zone_ids` field of a `LogisticCluster` record changes.
        Args:
            self (RecordSet): A set of `LogisticCluster` records.
        Returns:
            None.
        """
        for cluster in self:
            center_lon_total = sum(
                zone.center_lon for zone in cluster.zone_ids if zone.center_lon)
            center_lat_total = sum(
                zone.center_lat for zone in cluster.zone_ids if zone.center_lat)
            points_count = len(
                [zone for zone in cluster.zone_ids if zone.center_lon or zone.center_lat])

            if points_count > 0:
                cluster.center_lon = center_lon_total / points_count
                cluster.center_lat = center_lat_total / points_count
            else:
                cluster.center_lon = 0.0
                cluster.center_lat = 0.0

    @api.depends('slot_ids')
    def _compute_total_returned_slots(self:Type['Cluster']) -> None:
        """ Calculates the total number of returned slots in a `LogisticCluster` record.
        This method is called whenever the `slot_ids` field of a `LogisticCluster` record changes.
        Args:
            self (RecordSet): A set of `LogisticCluster` records.
        Returns:
            None.
        """
        for cluster in self:
            cluster.total_returned_slots = len(
                cluster.slot_ids.filtered(lambda slot: slot.is_returned))

    @api.depends('slot_ids')
    def _compute_total_delivered_slots(self:Type['Cluster']) -> None:
        """Computes the total number of delivered slots in a `LogisticCluster` record.
        This method is automatically called whenever the `slot_ids` field of a `LogisticCluster` record changes.
        Args:
            self (RecordSet): A set of `LogisticCluster` records.
        Returns:
            None.
        """
        for cluster in self:
            cluster.total_delivered_slots = len(
                cluster.slot_ids.filtered(lambda slot: slot.is_delivered))

    @api.depends('slot_ids')
    def _compute_reserved_volume_today(self:Type['Cluster']) -> None:
        """Computes the total reserved volume for the day in a `LogisticCluster` record.
        This method is automatically called whenever the `slot_ids` field of a `LogisticCluster` record changes.
        Args:
            self (RecordSet): A set of `LogisticCluster` records.
        Returns:
            None.
        """
        for cluster in self:
            slots_today = cluster.get_slots_by_date(
                from_date=TODAY, to_date=TODAY)
            total_reserved_volume = sum(slots_today.mapped("total_volume"))
            cluster.reserved_volume_today = total_reserved_volume

    @api.depends('slot_ids')
    def _compute_total_slots(self:Type['Cluster']) -> None:
        """
        Compute the total number of slots for a cluster by counting the number of slots
        returned by the get_slots_by_date method.

        :return: None
        """
        for cluster in self:
            # Call the get_slots_by_date method with all=True to retrieve all slots for the cluster.
            slots = cluster.get_slots_by_date(all_slots=True)
            # Count the number of slots.
            total_slots = len(slots)
            # Set the total_slots field on the cluster.
            cluster.total_slots = total_slots

    def get_slots_by_date(self, from_date: datetime = None, to_date: datetime = None, all_slots: bool = False) -> Union[Type['Cluster'], List[Type['Cluster']]]:
        """
        Get slots for the cluster based on the provided date range and/or return all slots.

        :param from_date: The start of the date range to search for slots.
        :type from_date: datetime
        :param to_date: The end of the date range to search for slots.
        :type to_date: datetime
        :param all_slots: Whether to return all slots for the cluster.
        :type all_slots: bool
        :return: A recordset of slots for the cluster based on the provided parameters.
        :rtype: recordset(logistic.slot)
        """
        if all_slots:
            # If all_slots is True, return all slots for the cluster.
            return self.env["logistic.slot"].search([("cluster_id", "=", self.id)])
        else:
            # Otherwise, return slots for the cluster based on the provided date range.
            return self.env["logistic.slot"].search([("cluster_id", "=", self.id), ("date", ">=", from_date), ("date", "<=", to_date)])

    @api.depends('zone_ids')
    def _compute_number_of_zones(self:Type['Cluster']) -> None:
        for record in self:
            record.number_of_zones = len(record.zone_ids)

    """Redirects"""

    def redirect_zones(self:Type['Cluster']) -> Dict:
        return {
            'name': 'Zones',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'logistic.zone',
            'type': 'ir.actions.act_window',
            'domain': [('cluster_id', '=', self.id)],
            'context': {'default_cluster_id': self.id}
        }

    def redirect_slots(self:Type['Cluster']) -> Dict:
        return {
            'name': 'Slots',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'logistic.slot',
            'type': 'ir.actions.act_window',
            'domain': [('cluster_id', '=', self.id)],
            'context': {'default_cluster_id': self.id}
        }

    def redirect_deliveries(self:Type['Cluster']) -> Dict:
        return {
            'name': 'Deliveries',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'logistic.delivery',
            'type': 'ir.actions.act_window',
            'domain': [('cluster_id', '=', self.id)],
            'context': {'default_cluster_id': self.id}
        }

    def redirect_customers(self:Type['Cluster']) -> Dict:
        return {
            'name': 'Customers',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'res.partner',
            'type': 'ir.actions.act_window',
            'domain': [('cluster_id', '=', self.id)],
            'context': {'default_cluster_id': self.id}
        }

    """Redirects"""


class LogisticZoneDateStatus(models.Model):
    _name = 'logistic.zone.status'
    _description = 'Zone Status'
    _rec_name = "summary"

    summary = fields.Text(
        string='Summary',
        compute="_compute_summary",
    )

    date = fields.Date(
        string="Date",
    )

    zone_id = fields.Many2one(
        "logistic.zone",
        string="Zone"
    )

    slot_ids = fields.One2many(
        "logistic.slot",
        "zone_status_id",
        string="Slots"
    )

    total_volume = fields.Float(
        string="Total volume",
        compute="_compute_total_volume"
    )

    total_assembly = fields.Float(
        string="Total assembly",
        compute="_compute_total_assembly"
    )

    planned_date_begin = fields.Datetime(
        string="Planned date begin",
        compute="_compute_planned_date_begin"
    )
    planned_date_end = fields.Datetime(
        string="Planned date end",
        compute="_compute_planned_date_end"
    )

    categories_summary = fields.Text(
        string='Categories summary',
        compute="_compute_categories_summary"
    )

    number_of_slots = fields.Integer(
        string="Number of slots",
        compute="_compute_number_of_slots"
    )

    def _compute_number_of_slots(self:Type['LogisticZoneDateStatus']) -> None:
        for status in self:
            status.number_of_slots = len(status.slot_ids)

    def redirect_slots(self):
        return {
            'name': 'Slots',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'logistic.slot',
            'type': 'ir.actions.act_window',
            'domain': [('zone_status_id', '=', self.id), ('date', '=', self.date)],
            'context': {'default_zone_status_id': self.id}
        }

    def _compute_categories_summary(self:Type['LogisticZoneDateStatus']) -> None:
        """Sets the categories summary, a field that is used in gantt view popup"""
        for status in self:
            status.categories_summary = status.get_categories_summary()

    def get_categories_summary(self:Type['LogisticZoneDateStatus']) -> str:
        """Returns a string with the categories summary"""
        categories_summary = {}
        categories_summary_str = ""
        for slot in self.slot_ids:
            if slot.sale_order_line_id.product_id.categ_id:
                if slot.sale_order_line_id.product_id.categ_id.name not in categories_summary.keys():
                    categories_summary[slot.sale_order_line_id.product_id.categ_id.name] = slot.total_volume
                else:
                    categories_summary[slot.sale_order_line_id.product_id.categ_id.name] += slot.total_volume
        for item in categories_summary:
            categories_summary_str += f"{item} :  {str(categories_summary[item])} \n"
        return categories_summary_str

    def _compute_planned_date_begin(self:Type['LogisticZoneDateStatus']) -> None:
        for status in self:
            date = status.date
            min_time = datetime.min.time()
            status.planned_date_begin = datetime.combine(date, min_time)

    def _compute_planned_date_end(self:Type['LogisticZoneDateStatus']) -> None:
        for status in self:
            date = status.date
            max_time = datetime.max.time()
            status.planned_date_end = datetime.combine(date, max_time)

    def _compute_summary(self:Type['LogisticZoneDateStatus']) -> None:
        for status in self:
            volume_str = "{:.2f}".format(status.total_volume)
            assembly_str = "{:.2f}".format(status.total_assembly)
            status.summary = f"CBM : {volume_str} - Hours : {assembly_str}"

    @api.depends("slot_ids")
    def _compute_total_volume(self:Type['LogisticZoneDateStatus']) -> None:
        for status in self:
            status.total_volume = sum(status.slot_ids.filtered(
                lambda x: x.is_delivered != True and x.status != 'cancelled').mapped("total_volume"))  # filter as required

    @api.depends("slot_ids")
    def _compute_total_assembly(self:Type['LogisticZoneDateStatus']) -> None:
        for status in self:
            status.total_assembly = sum(status.slot_ids.filtered(
                lambda x: x.is_delivered != True and x.status != 'cancelled').mapped("assembly_time"))

    @api.model
    def assign_order_date(self:Type['LogisticZoneDateStatus'], date: str) -> bool:
        """Assigns order to date through check date wizard"""
        order_id = http.request.session.get("order_id")
        if order_id:
            order = self.env["sale.order"].browse(order_id)
            if order:
                order.delivery_date = date
                return True

            else:
                raise UserError("Order not found")
        else:
            raise UserError("No order id available in context")

    @api.model
    def assign_order_installation_date(self:Type['LogisticZoneDateStatus'], date: str) -> bool:
        """Assigns order to date through check date wizard"""
        order_id = http.request.session.get("order_id")
        if order_id:
            order = self.env["sale.order"].browse(order_id)
            if order:
                order.installation_date = date
                return True

            else:
                raise UserError("Order not found")
        else:
            raise UserError("No order id available in context")


class Zone(models.Model):
    _name = 'logistic.zone'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Zone'
    _order = 'name'
    _rec_name = 'name'

    guid = fields.Char(
        string="GUID",
        readonly=True,
        copy=False,
        index=True
    )

    name = fields.Char(
        string='Name',
        required=True,
        translate=True,
        track_visibility='onchange',
    )

    description = fields.Text(
        string='Description',
        track_visibility='onchange',
    )


    cluster_id = fields.Many2one(
        'logistic.cluster',
        string='Cluster',
        required=True,
        domain="[('is_active','=',True)]",
        track_visibility='onchange',
    )

    district_ids = fields.One2many(
        "logistic.district",
        "zone_id",
        readonly=True,
        string="Zones"
    )

    zone_date_status_ids = fields.One2many(
        "logistic.zone.status",
        "zone_id",
        string="Zone Date Status"
    )

    geo_fence = fields.Text(
        string='Geofence data',
    )

    cluster_geo_fence = fields.Text(
        string='Cluster geo fence',
        compute="_compute_cluster_geo_fence"
    )

    other_cluster_geo_fence = fields.Text(
        string='Other cluster geo fence',
        compute="_compute_cluster_geo_fence"
    )

    center_lat = fields.Float(
        string="Center latitude",
        compute="_compute_center",
        digits=(16, 10)
    )

    center_lon = fields.Float(
        string="Center longitude",
        compute="_compute_center",
        digits=(16, 10)
    )

    number_of_districts = fields.Integer(
        string="Number of districts",
        compute="_compute_number_of_districts"
    )

    slot_ids = fields.One2many(
        "logistic.slot",
        "zone_id",
        string="Slots"
    )

    number_of_slots = fields.Integer(
        string="Number of slots",
        compute="_compute_number_of_slots"
    )

    number_of_deliveries = fields.Integer(
        string="Number of deliveries",
        compute="_compute_number_of_deliveries"
    )

    total_customers = fields.Integer(
        string="Total customers",
        compute="_compute_total_customers"
    )

    adjacent_zone_ids = fields.Many2many(
        comodel_name="logistic.zone", relation="zone_zone_rel", column1="zone1", column2="zone2", string="Adjacent Zones")

    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company, readonly=True)


    @api.model
    def create(self:Type['Zone'], values:Dict) -> Union(Type['Zone'], list[type['Zone']]):
        if isinstance(values, list):
            for val in values:
                val['guid'] = uuid.uuid4()
        elif isinstance(values, dict):
            values['guid'] = uuid.uuid4()
        result = super(Zone, self).create(values)
        return result

    def _compute_total_customers(self:Type['Zone']) -> None:
        for zone in self:
            zone.total_customers = self.env["res.partner"].search_count(
                [("zone_id", "=", zone.id)])

    def _compute_number_of_deliveries(self:Type['Zone']) -> None:
        for zone in self:
            zone.number_of_deliveries = len(
                self.env["logistic.slot"].search([("zone_id", "=", zone.id)]))

    def _compute_number_of_slots(self:Type['Zone']) -> None:
        for zone in self:
            zone.number_of_slots = len(zone.slot_ids)

    def _compute_number_of_districts(self:Type['Zone']) -> None:
        for zone in self:
            zone.number_of_districts = len(zone.district_ids)

    """Redirects"""

    def redirect_customers(self:Type['Zone']) -> Dict:
        return {
            'name': _('Customers'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'res.partner',
            'domain': [('zone_id', '=', self.id)],
            'context': {'default_zone_id': self.id},
            'target': 'current',
        }

    def redirect_delivery(self:Type['Zone']) -> Dict:
        return {
            'name': _('Deliveries'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'logistic.delivery',
            'type': 'ir.actions.act_window',
            'domain': [('zone_id', '=', self.id)]
        }

    def redirect_slots(self:Type['Zone']) -> Dict:
        return {
            'name': _('Slots'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'logistic.slot',
            'type': 'ir.actions.act_window',
            'domain': [('zone_id', '=', self.id)],
        }

    def redirect_districts(self:Type['Zone']) -> Dict:
        return {
            'name': _('Districts'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'logistic.district',
            'type': 'ir.actions.act_window',
            'domain': [('zone_id', '=', self.id)],
            'context': {'default_zone_id': self.id}
        }

    """Redirects"""

    @api.onchange('geo_fence')
    def _compute_center(self:Type['Zone']) -> None:
        for zone in self:
            if zone.geo_fence:
                center_lat_total = 0
                center_lat_count = 0
                center_lon_total = 0
                center_lon_count = 0
                geo_fence_json = json.loads(zone.geo_fence)
                for coordinate_pair in geo_fence_json:
                    center_lat_total += coordinate_pair.get("lat")
                    center_lat_count += 1
                    center_lon_total += coordinate_pair.get("lng")
                    center_lon_count += 1
                if center_lat_count and center_lon_count:
                    zone.center_lat = center_lat_total / center_lat_count
                    zone.center_lon = center_lon_total / center_lon_count
            else:
                zone.center_lat = 0
                zone.center_lon = 0

    def _compute_cluster_geo_fence(self:Type['Zone']) -> None:
        for rec in self:
            rec.cluster_geo_fence = json.dumps(rec.search(
                [("cluster_id", "=", rec.cluster_id.id), ('id', '!=', rec.id)]).mapped("geo_fence"))
            rec.other_cluster_geo_fence = json.dumps(rec.search(
                [("cluster_id", "!=", rec.cluster_id.id)]).mapped("geo_fence"))


class LogisticDistrict(models.Model):
    _name = 'logistic.district'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'District'
    rec_name = 'name'
    _order = 'name'

    guid = fields.Char(
        string="GUID",
        readonly=True,
        copy=False,
        index=True
    )

    name = fields.Char(
        string='Name',
        required=True,
        track_visibility='onchange',
    )

    description = fields.Text(
        string="Description",
        track_visibility='onchange',

    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.user.company_id.id
    )

    zone_id = fields.Many2one(
        'logistic.zone',
        string='Zone',
        track_visibility='onchange',
    )

    slot_ids = fields.One2many(
        "logistic.slot",
        "district_id",
        string="Slots"
    )

    number_of_slots = fields.Integer(
        string="Number of slots",
        compute="_compute_number_of_slots"
    )

    number_of_deliveries = fields.Integer(
        string="Number of deliveries",
        compute="_compute_number_of_deliveries"
    )

    total_customers = fields.Integer(
        string="Total customers",
        compute="_compute_total_customers"
    )

    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company, readonly=True)

    @api.model
    def create(self:Type['Zone'], values:Union(Dict, List[Dict])) -> Union([Type['Zone']]):
        if isinstance(values, list):
            for val in values:
                val['guid'] = uuid.uuid4()
        elif isinstance(values, dict):
            values['guid'] = uuid.uuid4()
        result = super(LogisticDistrict, self).create(values)
        return result

    def _compute_total_customers(self:Type['Zone']) -> None:
        for district in self:
            district.total_customers = self.env["res.partner"].search_count(
                [("district_id", "=", district.id)])

    @api.constrains('slot_ids')
    def _compute_number_of_slots(self:Type['Zone']) -> None:
        for record in self:
            record.number_of_slots = len(record.slot_ids)

    def _compute_number_of_deliveries(self:Type['Zone']) -> None:
        for record in self:
            record.number_of_deliveries = len(self.env["logistic.delivery"].search([
                                              ("district_ids", "in", record.id)]))

    def redirect_slots(self:Type['Zone']) -> Dict:
        return {
            'name': _('Slots'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'logistic.slot',
            'type': 'ir.actions.act_window',
            'domain': [('district_id', '=', self.id)],
        }

    def redirect_deliveries(self:Type['Zone']) -> Dict:
        return {
            'name': _('Deliveries'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'logistic.delivery',
            'type': 'ir.actions.act_window',
            'domain': [('district_ids', 'in', self.id)]
        }

    def redirect_customers(self:Type['Zone']) -> Dict:
        return {
            'name': _('Customers'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'res.partner',
            'type': 'ir.actions.act_window',
            'domain': [('district_ids', 'in', self.id)]
        }