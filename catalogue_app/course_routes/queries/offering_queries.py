from collections import defaultdict
from flask_babel import gettext
from catalogue_app.course_routes.utils import query_mysql, as_string, as_float, as_int, as_percent

# Note: String interpolation used for 'lang' and 'fiscal_year' because:
# a) They exist only as server-side variables, aren't user inputs
# b) From MySQL docs at	http://mysql-python.sourceforge.net/MySQLdb.html
# "Parameter placeholders can only be used to insert column values."
# "They can not be used for other parts of SQL, such as table names, etc."


# Decorator to time queries, if needed
# import time
def time_it(func):
	def wrapper(*args, **kwargs):
		t1 = time.time()
		result = func(*args, **kwargs)
		print('Func {0} took {1} sec'.format(func.__name__, round(time.time() - t1, 3)))
		return result
	return wrapper


def overall_numbers(fiscal_year, course_code):
	table_name = 'lsr{0}'.format(fiscal_year)
	
	query_open = "SELECT COUNT(DISTINCT offering_id) FROM {0} WHERE course_code = %s AND offering_status = 'Open - Normal';".format(table_name)
	open = query_mysql(query_open, (course_code,))
	
	query_delivered = "SELECT COUNT(DISTINCT offering_id) FROM {0} WHERE course_code = %s AND offering_status = 'Delivered - Normal';".format(table_name)
	delivered = query_mysql(query_delivered, (course_code,))
	
	query_cancelled = "SELECT COUNT(DISTINCT offering_id) FROM {0} WHERE course_code = %s AND offering_status = 'Cancelled - Normal';".format(table_name)
	cancelled = query_mysql(query_cancelled, (course_code,))
	
	query_client_reqs = "SELECT COUNT(DISTINCT offering_id) FROM {0} WHERE course_code = %s AND client != '' AND offering_status IN ('Open - Normal', 'Delivered - Normal');".format(table_name)
	client_reqs = query_mysql(query_client_reqs, (course_code,))
	
	query_regs = "SELECT COUNT(reg_id) FROM {0} WHERE course_code = %s AND reg_status = 'Confirmed';".format(table_name)
	regs = query_mysql(query_regs, (course_code,))
	
	query_no_shows = "SELECT SUM(no_show) FROM {0} WHERE course_code = %s;".format(table_name)
	no_shows = query_mysql(query_no_shows, (course_code,))
	
	results = [(gettext('Open Offerings'), as_int(open)),
			   (gettext('Delivered Offerings'), as_int(delivered)),
			   (gettext('Cancelled Offerings'), as_int(cancelled)),
			   (gettext('Client Requests'), as_int(client_reqs)),
			   (gettext('Registrations'), as_int(regs)),
			   (gettext('No-Shows'), as_int(no_shows))]
	return results


def offerings_per_region(fiscal_year, course_code):
	table_name = 'lsr{0}'.format(fiscal_year)
	query = """
		SELECT offering_region, COUNT(DISTINCT offering_id)
		FROM {0}
		WHERE course_code = %s AND offering_status IN ('Open - Normal', 'Delivered - Normal')
		GROUP BY offering_region;
		""".format(table_name)
	results = query_mysql(query, (course_code,))
	results = dict(results)
	
	# Process results into format required by Highcharts
	results_processed = {}
	regions = ['Atlantic', 'NCR', 'Ontario Region', 'Pacific', 'Prairie', 'Québec Region', 'Outside Canada']
	for region in regions:
		count = results.get(region, 0)
		results_processed[region] = count
	return results_processed


def _query_province_drilldown(fiscal_year, course_code, region):
	table_name = 'lsr{0}'.format(fiscal_year)
	query = """
		SELECT offering_province, COUNT(DISTINCT offering_id)
		FROM {0}
		WHERE course_code = %s AND offering_status IN ('Open - Normal', 'Delivered - Normal') AND offering_region = %s
		GROUP BY offering_province;
		""".format(table_name)
	results = query_mysql(query, (course_code, region))
	return results


def province_drilldown(fiscal_year, course_code):
	results_processed = defaultdict(list)
	regions = ['Atlantic', 'NCR', 'Ontario Region', 'Pacific', 'Prairie', 'Québec Region', 'Outside Canada']
	for region in regions:
		provinces = _query_province_drilldown(fiscal_year, course_code, region)
		provinces = [{'name': tup[0], 'y': tup[1], 'drilldown': tup[0]} for tup in provinces]
		results_processed[region].extend(provinces)
	return results_processed


def _query_city_drilldown(fiscal_year, course_code, province):
	table_name = 'lsr{0}'.format(fiscal_year)
	query = """
		SELECT offering_city, COUNT(DISTINCT offering_id)
		FROM {0}
		WHERE course_code = %s AND offering_status IN ('Open - Normal', 'Delivered - Normal') AND offering_province = %s
		GROUP BY offering_city;
		""".format(table_name)
	results = query_mysql(query, (course_code, province))
	return results


def city_drilldown(fiscal_year, course_code):
	results_processed = defaultdict(list)
	provinces = ['Alberta', 'British Columbia', 'Manitoba', 'NCR/RCN', 'New Brunswick',
				 'Newfoundland and Labrador', 'Northwest Territories', 'Nova Scotia',
				 'Nunavut', 'Ontario', 'Ontario_NCR', 'Prince Edward Island', 'Quebec',
				 'Québec_NCR', 'Saskatchewan', 'Yukon']
	for province in provinces:
		cities = _query_city_drilldown(fiscal_year, course_code, province)
		cities = [list(tup) for tup in cities]
		results_processed[province].extend(cities)
	return results_processed


def offerings_per_lang(fiscal_year, course_code):
	table_name = 'lsr{0}'.format(fiscal_year)
	query = """
		SELECT offering_language, COUNT(DISTINCT offering_id)
		FROM {0}
		WHERE course_code = %s AND offering_status IN ('Open - Normal', 'Delivered - Normal')
		GROUP BY offering_language;
		""".format(table_name)
	results = query_mysql(query, (course_code,))
	
	# Force 'English', 'French', and 'Bilingual' to be returned within dict
	results = dict(results)
	if 'English' not in results:
		results['English'] = 0
	if 'French' not in results:
		results['French'] = 0
	if 'Bilingual' not in results:
		results['Bilingual'] = 0
	return results


def offerings_cancelled(fiscal_year, course_code):
	table_name = 'lsr{0}'.format(fiscal_year)
	query = """
		SELECT SUM(a.Mars / b.Mars)
		FROM
			(SELECT COUNT(DISTINCT offering_id) AS Mars
			 FROM {0}
			 WHERE course_code = %s AND offering_status = 'Cancelled - Normal') AS a,
			 
			(SELECT COUNT(DISTINCT offering_id) AS Mars
			 FROM {0}
			 WHERE course_code = %s) AS b;
			""".format(table_name)
	results = query_mysql(query, (course_code, course_code))
	return as_percent(results)


# Need to separate global into separate function as using LIKE '%' too slow
def offerings_cancelled_global(fiscal_year):
	table_name = 'lsr{0}'.format(fiscal_year)
	query = """
		SELECT SUM(a.Mars / b.Mars)
		FROM
			(SELECT COUNT(DISTINCT offering_id) AS Mars
			 FROM {0}
			 WHERE business_type = 'Instructor-Led' AND offering_status = 'Cancelled - Normal') AS a,
			 
			(SELECT COUNT(DISTINCT offering_id) AS Mars
			 FROM {0}
			 WHERE business_type = 'Instructor-Led') AS b;
		""".format(table_name)
	results = query_mysql(query)
	return as_percent(results)


def avg_class_size(fiscal_year, course_code):
	table_name = 'lsr{0}'.format(fiscal_year)
	query = """
		SELECT AVG(class_size)
		FROM(
			SELECT COUNT(reg_id) AS class_size
			FROM {0}
			WHERE course_code = %s AND reg_status= 'Confirmed'
			GROUP BY offering_id
		) AS sub_table;
		""".format(table_name)
	results = query_mysql(query, (course_code,))
	return as_int(results)


# Need to separate global into separate function as using LIKE '%' too slow
def avg_class_size_global(fiscal_year):
	table_name = 'lsr{0}'.format(fiscal_year)
	query = """
		SELECT AVG(class_size)
		FROM(
			SELECT COUNT(reg_id) AS class_size
			FROM {0}
			WHERE reg_status= 'Confirmed' AND business_type = 'Instructor-Led'
			GROUP BY offering_id
		) AS sub_table;
		""".format(table_name)
	results = query_mysql(query)
	return as_int(results)


def avg_no_shows(fiscal_year, course_code):
	table_name = 'lsr{0}'.format(fiscal_year)
	query = """
		SELECT SUM(a.Mars / b.Mars)
		FROM
			(SELECT SUM(no_show) AS Mars
			 FROM {0}
			 WHERE course_code = %s) AS a,
			 
			(SELECT COUNT(DISTINCT offering_id) AS Mars
			 FROM {0}
			 WHERE course_code = %s AND offering_status IN ('Open - Normal', 'Delivered - Normal')) AS b;
		""".format(table_name)
	results = query_mysql(query, (course_code, course_code))
	return as_float(results)


# Need to separate global into separate function as using LIKE '%' too slow
def avg_no_shows_global(fiscal_year):
	table_name = 'lsr{0}'.format(fiscal_year)
	query = """
		SELECT SUM(a.Mars / b.Mars)
		FROM
			(SELECT SUM(no_show) AS Mars
			 FROM {0}
			 WHERE no_show = 1) AS a,
			 
			(SELECT COUNT(DISTINCT offering_id) AS Mars
			 FROM {0}
			 WHERE business_type = 'Instructor-Led' AND offering_status IN ('Open - Normal', 'Delivered - Normal')) AS b;
		""".format(table_name)
	results = query_mysql(query)
	return as_float(results)
