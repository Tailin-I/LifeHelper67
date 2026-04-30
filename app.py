import os
import sqlite3
from flask import Flask, render_template, request, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key_here_change_in_prod'
DB_PATH = 'forum.db'


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, email TEXT UNIQUE, password TEXT);
        CREATE TABLE IF NOT EXISTS forums (id INTEGER PRIMARY KEY, name TEXT, description TEXT);
        CREATE TABLE IF NOT EXISTS topics (id INTEGER PRIMARY KEY, forum_id INTEGER, title TEXT, author_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY, topic_id INTEGER, author_id INTEGER, content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    ''')
    if conn.execute('SELECT COUNT(*) FROM forums').fetchone()[0] == 0:
        conn.executemany('INSERT INTO forums (name, description) VALUES (?, ?)', [
            ('Новости и информация', 'Последние обновления проекта'),
            ('Технический раздел', 'Вопросы и помощь'),
            ('Правила', 'Условия использования форума'),
            ('Предложения', 'Идеи по улучшению'),
            ('Раздел проблем', 'Обсуждение неполадок'),
            ('Прочее', 'Свободное общение')
        ])
    conn.commit()
    conn.close()


@app.route('/')
def index():
    conn = get_db()
    forums = conn.execute('''
        SELECT f.*, COUNT(t.id) as topic_count 
        FROM forums f LEFT JOIN topics t ON f.id = t.forum_id 
        GROUP BY f.id
    ''').fetchall()
    conn.close()
    return render_template('index.html', forums=forums, user=session.get('user'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        u, e, p = request.form['username'], request.form['email'], request.form['password']
        conn = get_db()
        if conn.execute('SELECT id FROM users WHERE username=? OR email=?', (u, e)).fetchone():
            flash('Имя или email уже заняты', 'error')
        else:
            conn.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                         (u, e, generate_password_hash(p)))
            conn.commit()
            flash('Регистрация успешна! Войдите в систему.', 'success')
            return redirect(url_for('login'))
        conn.close()
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_input, password = request.form['username'], request.form['password']
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username=? OR email=?', (login_input, login_input)).fetchone()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user'] = user['username']
            return redirect(url_for('index'))
        flash('Неверный логин или пароль', 'error')
        conn.close()
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/forum/<int:forum_id>')
def forum(forum_id):
    conn = get_db()
    f = conn.execute('SELECT * FROM forums WHERE id=?', (forum_id,)).fetchone()
    topics = conn.execute('''
        SELECT t.*, u.username as author 
        FROM topics t JOIN users u ON t.author_id=u.id 
        WHERE t.forum_id=? ORDER BY t.created_at DESC
    ''', (forum_id,)).fetchall()
    conn.close()
    return render_template('forum.html', forum=f, topics=topics, user=session.get('user'))


@app.route('/new_topic/<int:forum_id>', methods=['GET', 'POST'])
def new_topic(forum_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        title, content = request.form['title'], request.form['content']
        conn = get_db()
        conn.execute('INSERT INTO topics (forum_id, title, author_id) VALUES (?, ?, ?)',
                     (forum_id, title, session['user_id']))
        tid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        conn.execute('INSERT INTO posts (topic_id, author_id, content) VALUES (?, ?, ?)',
                     (tid, session['user_id'], content))
        conn.commit()
        conn.close()
        return redirect(url_for('topic', topic_id=tid))
    return render_template('new_topic.html', forum_id=forum_id)


@app.route('/topic/<int:topic_id>', methods=['GET', 'POST'])
def topic(topic_id):
    conn = get_db()
    if request.method == 'POST' and 'user_id' in session:
        conn.execute('INSERT INTO posts (topic_id, author_id, content) VALUES (?, ?, ?)',
                     (topic_id, session['user_id'], request.form['content']))
        conn.commit()
        return redirect(url_for('topic', topic_id=topic_id))

    t = conn.execute('''
        SELECT t.*, u.username as author 
        FROM topics t JOIN users u ON t.author_id=u.id 
        WHERE t.id=?
    ''', (topic_id,)).fetchone()
    posts = conn.execute('''
        SELECT p.*, u.username as author 
        FROM posts p JOIN users u ON p.author_id=u.id 
        WHERE p.topic_id=? ORDER BY p.created_at ASC
    ''', (topic_id,)).fetchall()
    conn.close()
    return render_template('topic.html', topic=t, posts=posts, user=session.get('user'), user_id=session.get('user_id'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True)