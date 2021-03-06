import copy
import pickle
import time
from flask import Blueprint, redirect, render_template, request, session, url_for
from flask_babel import gettext
from catalogue_app import memo_dict
from catalogue_app.config import Config
from catalogue_app.course_routes.form import course_title_form, course_code_form
from catalogue_app.course_routes.queries import comment_queries, general_queries, learner_queries, map_queries
from catalogue_app.course_routes.queries import offering_queries, rating_queries, memoize_func
from catalogue_app import auth

# Instantiate blueprint
course = Blueprint('course', __name__)


# Make LAST_YEAR and THIS_YEAR available to all templates
LAST_YEAR = Config.LAST_YEAR
THIS_YEAR = Config.THIS_YEAR
@course.context_processor
def context_processor():
	return {'LAST_YEAR': LAST_YEAR.replace('_', '-'), 'THIS_YEAR': THIS_YEAR.replace('_', '-')}


# Search by course code
@course.route('/course-code-selection', methods=['GET', 'POST'])
@auth.login_required
def course_code_selection():
	lang = session.get('lang', 'en')
	form_name = ''
	form = course_code_form(lang, form_name)
	form = form(request.form)
	
	if request.method == 'POST' and form.validate():
		course_code = form.course_selection.data
		return redirect(url_for('course.course_result', course_code=course_code))
	return render_template('form.html', form=form, title=gettext("Selection"), button_val=gettext("Go"))


# Search by course title
@course.route('/course-title-selection', methods=['GET', 'POST'])
@auth.login_required
def course_title_selection():
	lang = session.get('lang', 'en')
	form_name = gettext('Course Title')
	form = course_title_form(lang, form_name)
	form = form(request.form)
	
	if request.method == 'POST' and form.validate():
		course_code = form.course_selection.data
		return redirect(url_for('course.course_result', course_code=course_code))
	return render_template('form.html', form=form, title=gettext("Selection"), button_val=gettext("Go"))


# Run queries and render template
@course.route('/course-result')
@auth.login_required
def course_result():
	# Get arguments from query string; if incomplete, return to selection page
	if 'course_code' not in request.args:
		return redirect(url_for('course.course_code_selection'))
	# Automatically escaped in Jinja2 (HTML templates) and MySQL queries
	course_code = request.args['course_code']
	lang = session.get('lang', 'en')
	
	# If course_code doesn't exist, render not_found.html
	course_title = general_queries.course_title(lang, THIS_YEAR, course_code)
	if not course_title:
		return render_template('not-found.html')
	
	# Check if course is online - needed for certain templates
	online_course = general_queries.online_course(THIS_YEAR, course_code)
	
	# Run queries and save in dict to be passed to templates
	# Check if already memoized in app var memo_dict
	if course_code in memo_dict:
		print('Using memoized values')
		return render_template('/course-page/main.html', pass_dict=copy.deepcopy(memo_dict[course_code]))
	else:
		print('Running query for first time')
		pass_dict = {
			#Global
			'course_code': course_code,
			'course_title': course_title,
			'online_course': online_course,
			# General
			'course_description': general_queries.course_description(lang, course_code),
			'course_info': general_queries.course_info(lang, course_code),
			# Dashboard - offerings
			'overall_numbers_LY': offering_queries.overall_numbers(LAST_YEAR, course_code),
			'overall_numbers_TY': offering_queries.overall_numbers(THIS_YEAR, course_code),
			'offerings_per_region': offering_queries.offerings_per_region(THIS_YEAR, course_code),
			'province_drilldown': offering_queries.province_drilldown(THIS_YEAR, course_code),
			'city_drilldown': offering_queries.city_drilldown(THIS_YEAR, course_code),
			'offerings_per_lang_LY': offering_queries.offerings_per_lang(LAST_YEAR, course_code),
			'offerings_per_lang_TY': offering_queries.offerings_per_lang(THIS_YEAR, course_code),
			'offerings_cancelled_global_LY': offering_queries.offerings_cancelled_global(LAST_YEAR),
			'offerings_cancelled_global_TY': offering_queries.offerings_cancelled_global(THIS_YEAR),
			'offerings_cancelled_LY': offering_queries.offerings_cancelled(LAST_YEAR, course_code),
			'offerings_cancelled_TY': offering_queries.offerings_cancelled(THIS_YEAR, course_code),
			'avg_class_size_global_LY': offering_queries.avg_class_size_global(LAST_YEAR),
			'avg_class_size_global_TY': offering_queries.avg_class_size_global(THIS_YEAR),
			'avg_class_size_LY': offering_queries.avg_class_size(LAST_YEAR, course_code),
			'avg_class_size_TY': offering_queries.avg_class_size(THIS_YEAR, course_code),
			'avg_no_shows_global_LY': round(offering_queries.avg_no_shows_global(LAST_YEAR), 1),
			'avg_no_shows_global_TY': round(offering_queries.avg_no_shows_global(THIS_YEAR), 1),
			'avg_no_shows_LY': round(offering_queries.avg_no_shows(LAST_YEAR, course_code), 1),
			'avg_no_shows_TY': round(offering_queries.avg_no_shows(THIS_YEAR, course_code), 1),
			# Dashboard - learners
			'regs_per_month': learner_queries.regs_per_month(THIS_YEAR, course_code),
			'top_5_depts': learner_queries.top_5_depts(lang, THIS_YEAR, course_code),
			'top_5_classifs': learner_queries.top_5_classifs(THIS_YEAR, course_code),
			# Maps
			'offering_city_counts': map_queries.offering_city_counts(THIS_YEAR, course_code),
			'learner_city_counts': map_queries.learner_city_counts(THIS_YEAR, course_code),
			# Ratings
			'all_ratings': rating_queries.all_ratings(course_code, 'en'),
			# Comments
			'general_comments': comment_queries.fetch_comments(course_code, 'Comment - General'),
			'technical_comments': comment_queries.fetch_comments(course_code, 'Comment - Technical'),
			'language_comments': comment_queries.fetch_comments(course_code, 'Comment - OL'),
			'performance_comments': comment_queries.fetch_comments(course_code, 'Comment - Performance'),
			# Categorical and yes/no questions
			'reason_to_participate': comment_queries.fetch_categorical(course_code, 'Reason to Participate'),
			'technical_issues': comment_queries.fetch_categorical(course_code, 'Technical Issues'),
			'languages_available': comment_queries.fetch_categorical(course_code, 'OL Available '),
			'tools_used': comment_queries.fetch_categorical(course_code, 'GCcampus Tools Used'),
			'prepared_by': comment_queries.fetch_categorical(course_code, 'Prep')
		}
		# Memoize new query results
		memo_dict[course_code] = pass_dict
		return render_template('/course-page/main.html', pass_dict=copy.deepcopy(memo_dict[course_code]))


# Run queries for all course codes, save to dict, and pickle
@course.route('/memoize-all')
@auth.login_required
def memoize_all():
	t1 = time.time()
	course_codes = general_queries.all_course_codes(THIS_YEAR)
	for code in course_codes:
		print(code)
		vals = memoize_func.get_vals(code)
		memo_dict[code] = vals
	t2 = time.time()
	# Save memo_dict to binary file
	with open('memo.pickle', 'wb') as f:
		pickle.dump(memo_dict, f, protocol=pickle.HIGHEST_PROTOCOL)
	return '<h1>Done!</h1><p>Time elapsed: {0}</p><p>Another great day in DIS.</p>'.format(t2 - t1)


# Coming soon
@course.route('/departmental')
@auth.login_required
def departmental():
	return render_template('departmental.html')


# Coming soon
@course.route('/fr')
@auth.login_required
def fr():
	return render_template('fr.html')
