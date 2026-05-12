import os
import sqlite3
from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'OLEG_SONYA_I_SLAVA_BOGI_ETOGO_MIRA_GOIDA_52_676767_LIFE_HELPER_SLAVA_VELIKOI_KITAISKOI_NARODNOI_RESPUBLIKI_HAIL_HIHIHIHIHIHIHIHIHIHIIHHIHI'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# настройки загрузки файлов
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


DB_PATH = 'forum.db'


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# база данных
def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            password TEXT,
            is_moderator INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS forums (
            id INTEGER PRIMARY KEY,
            name TEXT,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY,
            forum_id INTEGER,
            title TEXT,
            author_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_closed INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY,
            topic_id INTEGER,
            author_id INTEGER,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reply_to_id INTEGER REFERENCES posts(id)
        );
        CREATE TABLE IF NOT EXISTS post_images (
            id INTEGER PRIMARY KEY,
            post_id INTEGER,
            filename TEXT,
            original_filename TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            post_id INTEGER,
            UNIQUE(user_id, post_id)
        );
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            is_closed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER,
            sender_id INTEGER,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_read INTEGER DEFAULT 0,
            FOREIGN KEY (chat_id) REFERENCES chat_sessions(id),
            FOREIGN KEY (sender_id) REFERENCES users(id)
        );
    ''')

    try:
        conn.execute('ALTER TABLE users ADD COLUMN is_moderator INTEGER DEFAULT 0')
    except:
        pass

    try:
        conn.execute('ALTER TABLE topics ADD COLUMN is_closed INTEGER DEFAULT 0')
    except:
        pass

    if conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
        conn.execute('''
            INSERT INTO users (username, email, password, is_moderator)
            VALUES (?, ?, ?, ?)
        ''', ('admin', 'admin@lifehelper.local', generate_password_hash('admin123'), 1))
        conn.commit()

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


# проверка прав модера
def moderator_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        conn = get_db()
        user = conn.execute('SELECT is_moderator FROM users WHERE id = ?',
                            (session['user_id'],)).fetchone()
        conn.close()
        if not user or not user['is_moderator']:
            flash('У вас нет прав модератора', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


# главная страница
@app.route('/')
def index():
    conn = get_db()
    stats = conn.execute('''
        SELECT (SELECT COUNT(*) FROM users) as users,
               (SELECT COUNT(*) FROM topics) as topics,
               (SELECT COUNT(*) FROM posts) as posts
    ''').fetchone()
    forums = conn.execute('''
        SELECT f.*, COUNT(t.id) as topic_count
        FROM forums f LEFT JOIN topics t ON f.id = t.forum_id
        GROUP BY f.id
    ''').fetchall()
    conn.close()
    return render_template('index.html', forums=forums, user=session.get('user'), stats=stats)


# регистрация
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


# вход
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_input, password = request.form['username'], request.form['password']
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username=? OR email=?',
                            (login_input, login_input)).fetchone()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user'] = user['username']
            return redirect(url_for('index'))
        flash('Неверный логин или пароль', 'error')
        conn.close()
    return render_template('login.html')


# выход
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# просмотр форума
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


# создание темы
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

        if 'images' in request.files:
            files = request.files.getlist('images')
            for file in files:
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                    unique_filename = f"{timestamp}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    file.save(file_path)
                    conn.execute('INSERT INTO post_images (post_id, filename, original_filename) VALUES (?, ?, ?)',
                                 (tid, unique_filename, filename))

        conn.commit()
        conn.close()
        return redirect(url_for('topic', topic_id=tid))
    return render_template('new_topic.html', forum_id=forum_id)


# лайк поста
@app.route('/like/<int:post_id>', methods=['POST'])
def like_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db()
    exists = conn.execute('SELECT id FROM likes WHERE user_id=? AND post_id=?',
                          (user_id, post_id)).fetchone()
    if exists:
        conn.execute('DELETE FROM likes WHERE user_id=? AND post_id=?', (user_id, post_id))
    else:
        conn.execute('INSERT INTO likes (user_id, post_id) VALUES (?, ?)', (user_id, post_id))
    conn.commit()
    topic = conn.execute('SELECT topic_id FROM posts WHERE id=?', (post_id,)).fetchone()
    conn.close()
    return redirect(url_for('topic', topic_id=topic['topic_id']))


# удаление поста
@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    post = conn.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
    if not post:
        conn.close()
        return redirect(url_for('index'))

    user = conn.execute('SELECT is_moderator FROM users WHERE id = ?',
                        (session['user_id'],)).fetchone()

    if user['is_moderator'] or post['author_id'] == session['user_id']:
        images = conn.execute('SELECT filename FROM post_images WHERE post_id = ?', (post_id,)).fetchall()
        for img in images:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], img['filename'])
            if os.path.exists(file_path):
                os.remove(file_path)

        conn.execute('DELETE FROM likes WHERE post_id = ?', (post_id,))
        conn.execute('DELETE FROM post_images WHERE post_id = ?', (post_id,))
        conn.execute('DELETE FROM posts WHERE id = ?', (post_id,))
        conn.commit()
        flash('Сообщение удалено', 'success')
    else:
        flash('У вас нет прав для удаления этого сообщения', 'error')

    topic_id = post['topic_id']
    conn.close()
    return redirect(url_for('topic', topic_id=topic_id))


# закрыть/открыть тему
@app.route('/toggle_topic/<int:topic_id>', methods=['POST'])
@moderator_required
def toggle_topic(topic_id):
    conn = get_db()
    topic = conn.execute('SELECT * FROM topics WHERE id = ?', (topic_id,)).fetchone()
    if topic:
        new_status = 0 if topic['is_closed'] else 1
        conn.execute('UPDATE topics SET is_closed = ? WHERE id = ?',
                     (new_status, topic_id))
        conn.commit()
        status_text = 'закрыта' if new_status else 'открыта'
        flash(f'Тема {status_text}', 'success')
    conn.close()
    return redirect(url_for('topic', topic_id=topic_id))


# удаление темы
@app.route('/delete_topic/<int:topic_id>', methods=['POST'])
@moderator_required
def delete_topic(topic_id):
    conn = get_db()
    topic = conn.execute('SELECT forum_id FROM topics WHERE id = ?', (topic_id,)).fetchone()
    if topic:
        posts = conn.execute('SELECT id FROM posts WHERE topic_id = ?', (topic_id,)).fetchall()
        for p in posts:
            images = conn.execute('SELECT filename FROM post_images WHERE post_id = ?', (p['id'],)).fetchall()
            for img in images:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], img['filename'])
                if os.path.exists(file_path):
                    os.remove(file_path)

        conn.execute('DELETE FROM likes WHERE post_id IN (SELECT id FROM posts WHERE topic_id = ?)',
                     (topic_id,))
        conn.execute('DELETE FROM post_images WHERE post_id IN (SELECT id FROM posts WHERE topic_id = ?)', (topic_id,))
        conn.execute('DELETE FROM posts WHERE topic_id = ?', (topic_id,))
        conn.execute('DELETE FROM topics WHERE id = ?', (topic_id,))
        conn.commit()
        flash('Тема удалена', 'success')
        return redirect(url_for('forum', forum_id=topic['forum_id']))
    conn.close()
    return redirect(url_for('index'))


# просмотр темы
@app.route('/topic/<int:topic_id>', methods=['GET', 'POST'])
def topic(topic_id):
    conn = get_db()
    if request.method == 'POST' and 'user_id' in session:
        content = request.form['content']
        reply_to = request.form.get('reply_to_id') or None
        conn.execute('INSERT INTO posts (topic_id, author_id, content, reply_to_id) VALUES (?, ?, ?, ?)',
                     (topic_id, session['user_id'], content, reply_to))
        pid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]

        if 'images' in request.files:
            files = request.files.getlist('images')
            for file in files:
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                    unique_filename = f"{timestamp}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    file.save(file_path)
                    conn.execute('INSERT INTO post_images (post_id, filename, original_filename) VALUES (?, ?, ?)',
                                 (pid, unique_filename, filename))

        conn.commit()
        return redirect(url_for('topic', topic_id=topic_id))

    t = conn.execute('''
        SELECT t.*, u.username as author, f.name as forum_name
        FROM topics t
        JOIN users u ON t.author_id=u.id
        JOIN forums f ON t.forum_id = f.id
        WHERE t.id=?
    ''', (topic_id,)).fetchone()

    user_is_moderator = False
    if session.get('user_id'):
        mod_check = conn.execute('SELECT is_moderator FROM users WHERE id = ?',
                                 (session['user_id'],)).fetchone()
        user_is_moderator = mod_check['is_moderator'] if mod_check else False

    posts = conn.execute('''
        SELECT p.*, u.username as author, ru.username as reply_to_author,
               (SELECT COUNT(*) FROM likes WHERE post_id = p.id) as likes,
               (SELECT COUNT(*) FROM likes WHERE post_id = p.id AND user_id = ?) as user_liked
        FROM posts p
        JOIN users u ON p.author_id=u.id
        LEFT JOIN posts rp ON p.reply_to_id = rp.id
        LEFT JOIN users ru ON rp.author_id = ru.id
        WHERE p.topic_id=? ORDER BY p.created_at ASC
    ''', (session.get('user_id'), topic_id)).fetchall()

    posts_with_images = []
    for post in posts:
        images = conn.execute('SELECT * FROM post_images WHERE post_id = ?', (post['id'],)).fetchall()
        posts_with_images.append({'post': post, 'images': images})

    conn.close()
    return render_template('topic.html', topic=t, posts=posts_with_images, user=session.get('user'),
                           user_id=session.get('user_id'), user_is_moderator=user_is_moderator)


# чат помощи
@app.route('/help_chat')
def help_chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    user_id = session['user_id']
    is_moderator = conn.execute('SELECT is_moderator FROM users WHERE id = ?', (user_id,)).fetchone()['is_moderator']

    if is_moderator:
        chats = conn.execute('''
            SELECT cs.id, u.username,
                   (SELECT content FROM chat_messages WHERE chat_id = cs.id ORDER BY created_at DESC LIMIT 1) as last_message,
                   (SELECT COUNT(*) FROM chat_messages WHERE chat_id = cs.id AND is_read = 0 AND sender_id != ?) as unread_count
            FROM chat_sessions cs
            JOIN users u ON cs.user_id = u.id
            WHERE cs.is_closed = 0
            ORDER BY cs.created_at DESC
        ''', (user_id,)).fetchall()
    else:
        chats = conn.execute('''
            SELECT cs.id, cs.is_closed,
                   (SELECT COUNT(*) FROM chat_messages WHERE chat_id = cs.id AND is_read = 0 AND sender_id != ?) as unread_count
            FROM chat_sessions cs
            WHERE cs.user_id = ?
            ORDER BY cs.created_at DESC
        ''', (user_id, user_id)).fetchall()

    conn.close()
    return render_template('help_chat.html', chats=chats, is_moderator=is_moderator, user=session.get('user'))


# чат помощи - комната
@app.route('/help_chat/<int:chat_id>', methods=['GET', 'POST'])
def help_chat_room(chat_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    user_id = session['user_id']
    is_moderator = conn.execute('SELECT is_moderator FROM users WHERE id = ?',
                                (user_id,)).fetchone()['is_moderator']

    if is_moderator:
        chat = conn.execute('''
            SELECT cs.*, u.username
            FROM chat_sessions cs
            JOIN users u ON cs.user_id = u.id
            WHERE cs.id = ?
        ''', (chat_id,)).fetchone()
    else:
        chat = conn.execute('SELECT * FROM chat_sessions WHERE id = ? AND user_id = ?',
                            (chat_id, user_id)).fetchone()

    if not chat:
        conn.close()
        flash('Чат не найден', 'error')
        return redirect(url_for('help_chat'))

    if chat and chat['is_closed'] and not is_moderator:
        flash('Этот чат закрыт', 'error')
        conn.close()
        return redirect(url_for('help_chat'))

    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        if content:
            conn.execute('''
                INSERT INTO chat_messages (chat_id, sender_id, content)
                VALUES (?, ?, ?)
            ''', (chat_id, user_id, content))
            conn.commit()
            conn.execute('''
                UPDATE chat_messages SET is_read = 1
                WHERE chat_id = ? AND sender_id != ?
            ''', (chat_id, user_id))
            conn.commit()
            return redirect(url_for('help_chat_room', chat_id=chat_id))

    messages = conn.execute('''
        SELECT cm.*, u.username, u.is_moderator
        FROM chat_messages cm
        JOIN users u ON cm.sender_id = u.id
        WHERE cm.chat_id = ?
        ORDER BY cm.created_at ASC
    ''', (chat_id,)).fetchall()

    conn.execute('''
        UPDATE chat_messages SET is_read = 1
        WHERE chat_id = ? AND sender_id != ? AND is_read = 0
    ''', (chat_id, user_id))
    conn.commit()
    conn.close()
    return render_template('help_chat_room.html', chat=chat, messages=messages,
                           is_moderator=is_moderator, user=session.get('user'))


# создать чат
@app.route('/help_chat/create', methods=['POST'])
def create_help_chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    user_id = session['user_id']
    existing = conn.execute('''
        SELECT id FROM chat_sessions
        WHERE user_id = ? AND is_closed = 0
    ''', (user_id,)).fetchone()

    if existing:
        conn.close()
        return redirect(url_for('help_chat_room', chat_id=existing['id']))

    cursor = conn.execute('''
        INSERT INTO chat_sessions (user_id, is_closed) VALUES (?, 0)
    ''', (user_id,))
    chat_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return redirect(url_for('help_chat_room', chat_id=chat_id))


# закрыть чат
@app.route('/help_chat/<int:chat_id>/close', methods=['POST'])
@moderator_required
def close_help_chat(chat_id):
    conn = get_db()
    conn.execute('UPDATE chat_sessions SET is_closed = 1 WHERE id = ?', (chat_id,))
    conn.commit()
    conn.close()
    flash('Чат закрыт', 'success')
    return redirect(url_for('help_chat'))


# политика конфиденциальности
@app.route('/privacy')
def privacy():
    return render_template('privacy.html', user=session.get('user'))


# загруженные файлы
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# скачать файл
@app.route('/uploads/<filename>/download')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)


# создать тему через api
@app.route('/api/topic', methods=['POST'])
def api_create_topic():
    data = request.get_json()

    if not data or 'title' not in data or 'forum_id' not in data or 'content' not in data:
        return jsonify({'error': 'Missing required fields: title, forum_id, content'}), 400

    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    conn = get_db()

    forum = conn.execute('SELECT id FROM forums WHERE id = ?', (data['forum_id'],)).fetchone()
    if not forum:
        conn.close()
        return jsonify({'error': 'Forum not found'}), 404

    conn.execute('''
        INSERT INTO topics (forum_id, title, author_id, is_closed)
        VALUES (?, ?, ?, 0)
    ''', (data['forum_id'], data['title'], session['user_id']))

    topic_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]

    conn.execute('''
        INSERT INTO posts (topic_id, author_id, content)
        VALUES (?, ?, ?)
    ''', (topic_id, session['user_id'], data['content']))

    conn.commit()
    conn.close()

    return jsonify({
        'message': 'Topic created',
        'topic_id': topic_id,
        'title': data['title']
    }), 201


# удалить тему через api
@app.route('/api/topic/<int:topic_id>', methods=['DELETE'])
def api_delete_topic(topic_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    conn = get_db()

    topic = conn.execute('SELECT author_id, forum_id FROM topics WHERE id = ?', (topic_id,)).fetchone()
    if not topic:
        conn.close()
        return jsonify({'error': 'Topic not found'}), 404

    user = conn.execute('SELECT is_moderator FROM users WHERE id = ?', (session['user_id'],)).fetchone()

    if not user['is_moderator'] and topic['author_id'] != session['user_id']:
        conn.close()
        return jsonify({'error': 'Permission denied'}), 403

    conn.execute('DELETE FROM likes WHERE post_id IN (SELECT id FROM posts WHERE topic_id = ?)', (topic_id,))
    conn.execute('DELETE FROM post_images WHERE post_id IN (SELECT id FROM posts WHERE topic_id = ?)', (topic_id,))
    conn.execute('DELETE FROM posts WHERE topic_id = ?', (topic_id,))
    conn.execute('DELETE FROM topics WHERE id = ?', (topic_id,))

    conn.commit()
    conn.close()

    return jsonify({'message': 'Topic deleted', 'topic_id': topic_id})


if __name__ == '__main__':
    init_db()
    app.run(debug=True)