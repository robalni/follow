#!/usr/bin/python3

from flask import Flask, render_template
from datetime import datetime
import channels

app = Flask(__name__)

@app.route('/')
def page_main():
    context = {
        'posts': channels.get_all_posts(),
        'now': datetime.now(),
    }
    return render_template('main.html', **context)

@app.route('/channels/')
def page_channels():
    context = {
        'title': 'Channels',
        'channels': channels.get_channels(),
    }
    return render_template('channels.html', **context)

def format_time(value):
    import time
    format_string = '%Y-%m-%d %T %z'
    if type(value) is time.struct_time:
        return time.strftime(format_string, value)
    else:
        return value.strftime(format_string)

app.jinja_env.filters['timefmt'] = format_time
app.run()
