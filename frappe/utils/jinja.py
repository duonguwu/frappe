# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

def get_jenv():
	import frappe
	from frappe.utils.safe_exec import get_safe_globals

	if not getattr(frappe.local, 'jenv', None):
		from jinja2 import DebugUndefined
		from jinja2.sandbox import SandboxedEnvironment

		# frappe will be loaded last, so app templates will get precedence
		jenv = SandboxedEnvironment(
			loader=get_jloader(),
			undefined=DebugUndefined
		)
		set_filters(jenv)

		jenv.globals.update(get_safe_globals())
		jenv.globals.update(get_jenv_customization('methods'))
		jenv.globals.update({
			'component': component,
			'c': component,
			'resolve_class': resolve_class,
			'inspect': inspect
		})

		frappe.local.jenv = jenv

	return frappe.local.jenv

def get_template(path):
	return get_jenv().get_template(path)

def get_email_from_template(name, args):
	from jinja2 import TemplateNotFound

	args = args or {}
	try:
		message = get_template('templates/emails/' + name + '.html').render(args)
	except TemplateNotFound as e:
		raise e

	try:
		text_content = get_template('templates/emails/' + name + '.txt').render(args)
	except TemplateNotFound:
		text_content = None

	return (message, text_content)

def validate_template(html):
	"""Throws exception if there is a syntax error in the Jinja Template"""
	import frappe
	from jinja2 import TemplateSyntaxError

	jenv = get_jenv()
	try:
		jenv.from_string(html)
	except TemplateSyntaxError as e:
		frappe.msgprint('Line {}: {}'.format(e.lineno, e.message))
		frappe.throw(frappe._("Syntax error in template"))

def render_template(template, context, is_path=None, safe_render=True):
	'''Render a template using Jinja

	:param template: path or HTML containing the jinja template
	:param context: dict of properties to pass to the template
	:param is_path: (optional) assert that the `template` parameter is a path
	:param safe_render: (optional) prevent server side scripting via jinja templating
	'''

	from frappe import get_traceback, throw
	from jinja2 import TemplateError

	if not template:
		return ""

	if (is_path or guess_is_path(template)):
		return get_jenv().get_template(template).render(context)
	else:
		if safe_render and ".__" in template:
			throw("Illegal template")
		try:
			return get_jenv().from_string(template).render(context)
		except TemplateError:
			throw(title="Jinja Template Error", msg="<pre>{template}</pre><pre>{tb}</pre>".format(template=template, tb=get_traceback()))

def guess_is_path(template):
	# template can be passed as a path or content
	# if its single line and ends with a html, then its probably a path
	if not '\n' in template and '.' in template:
		extn = template.rsplit('.')[-1]
		if extn in ('html', 'css', 'scss', 'py'):
			return True

	return False


def get_jloader():
	import frappe
	if not getattr(frappe.local, 'jloader', None):
		from jinja2 import ChoiceLoader, PackageLoader, PrefixLoader

		if frappe.local.flags.in_setup_help:
			apps = ['frappe']
		else:
			apps = frappe.get_hooks('template_apps')
			if not apps:
				apps = frappe.local.flags.web_pages_apps or frappe.get_installed_apps(sort=True)
				apps.reverse()

		if not "frappe" in apps:
			apps.append('frappe')

		frappe.local.jloader = ChoiceLoader(
			# search for something like app/templates/...
			[PrefixLoader(dict(
				(app, PackageLoader(app, ".")) for app in apps
			))]

			# search for something like templates/...
			+ [PackageLoader(app, ".") for app in apps]
		)

	return frappe.local.jloader

def set_filters(jenv):
	import frappe
	from frappe.utils import global_date_format, cint, cstr, flt, markdown
	from frappe.website.utils import get_shade, abs_url

	jenv.filters["global_date_format"] = global_date_format
	jenv.filters["markdown"] = markdown
	jenv.filters["json"] = frappe.as_json
	jenv.filters["get_shade"] = get_shade
	jenv.filters["len"] = len
	jenv.filters["int"] = cint
	jenv.filters["str"] = cstr
	jenv.filters["flt"] = flt
	jenv.filters["abs_url"] = abs_url

	if frappe.flags.in_setup_help:
		return

	jenv.filters.update(get_jenv_customization('filters'))


def get_jenv_customization(customization_type):
	'''Returns a dict with filter/method name as key and definition as value'''

	import frappe

	out = {}
	if not getattr(frappe.local, "site", None):
		return out

	values = frappe.get_hooks("jenv", {}).get(customization_type)
	if not values:
		return out

	for value in values:
		fn_name, fn_string = value.split(":")
		out[fn_name] = frappe.get_attr(fn_string)

	return out


def component(name, **kwargs):
	from jinja2 import TemplateNotFound

	template_name = 'templates/components/' + name + '.html'
	jenv = get_jenv()

	try:
		source = jenv.loader.get_source(jenv, template_name)[0]
	except TemplateNotFound:
		return '<pre>Component "{0}" not found</pre>'.format(name)

	attributes, html = parse_front_matter_attrs_and_html(source)
	context = {}
	context.update(attributes)
	context.update(kwargs)

	if 'class' in context:
		context['class'] = resolve_class(context['class'])
	else:
		context['class'] = ''

	return get_jenv().from_string(html).render(context)

def resolve_class(classes):
	import frappe

	if classes is None:
		return ''

	if isinstance(classes, frappe.string_types):
		return classes

	if isinstance(classes, (list, tuple)):
		return ' '.join([resolve_class(c) for c in classes]).strip()

	if isinstance(classes, dict):
		return ' '.join([classname for classname in classes if classes[classname]]).strip()

	return classes

def parse_front_matter_attrs_and_html(source):
	from frontmatter import Frontmatter

	html = source
	attributes = {}

	if not source.startswith('---'):
		return attributes, html

	try:
		res = Frontmatter.read(source)
		if res['attributes']:
			attributes = res['attributes']
			html = res['body']
	except Exception as e:
		print('Error parsing Frontmatter in template: ' + e)

	return attributes, html

def inspect(var, render=True):
	context = { "var": var }
	if render:
		html = "<pre>{{ var | pprint | e }}</pre>"
	else:
		html = ""
	return get_jenv().from_string(html).render(context)
