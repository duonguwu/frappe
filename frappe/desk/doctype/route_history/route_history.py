# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.deferred_insert import deferred_insert
from frappe.model.document import Document


class RouteHistory(Document):
	pass


def flush_old_route_records():
	"""Deletes all route records except last 500 records per user"""

	records_to_keep_limit = 500
	users = frappe.db.sql('''
		SELECT `user`
		FROM `tabRoute History`
		GROUP BY `user`
		HAVING count(`name`) > %(limit)s
	''', {
		"limit": records_to_keep_limit
	})

	for user in users:
		user = user[0]
		last_record_to_keep = frappe.db.get_all('Route History',
			filters={'user': user},
			limit=1,
			limit_start=500,
			fields=['modified'],
			order_by='modified desc'
		)

		frappe.db.delete("Route History", {
			"modified": ("<=", last_record_to_keep[0].modified),
			"user": user
		})

@frappe.whitelist()
def deferred_insert_route_history(routes):
	routes_record = []

	if isinstance(routes, str):
		routes = json.loads(routes)

	for route_doc in routes:
		routes_record.append({
			"user": frappe.session.user,
			"route": route_doc.get("route"),
			"creation": route_doc.get("creation")
		})

	deferred_insert("Route History", json.dumps(routes_record))
