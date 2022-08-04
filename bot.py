import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import KeyboardButton as kb
from aiogram.types import InlineKeyboardButton as ikb
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher.filters import Text
import requests as rq
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import psycopg2
import hashlib
import json
import datetime as dt
import matplotlib.pyplot as plt
import os

DATABASE_URL = os.environ['DATABASE_URL']
conn = psycopg2.connect(DATABASE_URL, sslmode='require')

TOKEN = os.environ['BOT_TOKEN']
bot = Bot(token=TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot, storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

@dp.message_handler(commands="start")
async def start_handler(message: types.Message):
    try:
        cur = conn.cursor()
        cur.execute("SELECT username FROM users WHERE tg_username='" + message.from_user.username + "';")
        un = cur.fetchone()
        if un == None:
            buttons = [
                types.InlineKeyboardButton(text="Зарегестрироваться", callback_data="reg_button"),
                types.InlineKeyboardButton(text="Войти", callback_data="login_button")
            ]
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(*buttons)
            await message.answer('Это telegram-бот проекта KeepYourMoney, с информацией о котором подробнее вы можете ознакомиться по <a href="https://keepyourmoney.ru">ссылке</a>')
            await message.answer('Чтобы использовать бота необходимо зарегестрироваться или войти (если вы ранее регистрировались через сайт) в свой аккаунт', reply_markup=keyboard)
        else:
            keyb = types.InlineKeyboardMarkup()
            keyb.add(types.InlineKeyboardButton(text="Привязать новый аккаунт", callback_data="newlog"), types.InlineKeyboardButton(text="Зарегестрироваться", callback_data="reg_button"))
            keyr = types.ReplyKeyboardMarkup()
            keyr.add(types.KeyboardButton(text="Запустить приложение"))
            await message.answer('Вы уже привязывали аккаунт KeepYourMoney к вашему telegram-аккаунту, так что можете пользоваться им как ' + un[0], reply_markup=keyr)
            await message.answer('Либо войдите в новый аккаунт, либо зарегистрируйте новый', reply_markup=keyb)
    except Exception as e:
        print(e)
        await message.answer("Ошибка на сервере")

class LoginStatus(StatesGroup):
    waiting_username = State()
    waiting_password = State()

class RegStatus(StatesGroup):
    wait_user = State()
    wait_pass = State()

class AddExpStatus(StatesGroup):
    cat = State()
    title = State()
    summa = State()

class DelCatStatus(StatesGroup):
    rem = State()

class AddCatStatus(StatesGroup):
    cat_name = State()

def pwd256(pwd):
    return hashlib.sha256(pwd.encode('utf-8')).hexdigest()

@dp.callback_query_handler(text="newlog")
async def newlog_button(call: types.CallbackQuery):
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE tg_username='" + call.message.chat.username + "';")
        print(call.message.chat.username, cur.rowcount)
        keyb = types.ReplyKeyboardMarkup()
        keyb.add(kb("Отмена"))
        await call.message.answer("Для входа введите имя пользователя: ", reply_markup=keyb)
        cur.close()
        conn.commit()
        await LoginStatus.waiting_username.set()
    except Exception as e:
        print(e)
        await call.message.answer("Ошибка на сервере")

@dp.callback_query_handler(text="login_button")
async def login_button(call: types.CallbackQuery):
    try:
        cur = conn.cursor()
        cur.execute("SELECT username FROM users WHERE tg_username='" + call.message.from_user.username + "';")
        fetc = cur.fetchone()
        if fetc == None:
            keyb = types.ReplyKeyboardMarkup()
            keyb.add(kb("Отмена"))
            await call.message.answer("Для входа введите имя пользователя: ", reply_markup=keyb)
            await LoginStatus.waiting_username.set()
        else:
            await call.message.answer("К вашему аккаунту уже привязан аккаунт")
    except Exception as e:
        print(e)
        await call.message.answer("Ошибка на сервере")

@dp.message_handler(state=LoginStatus.waiting_username)
async def login_username(message: types.Message, state: FSMContext):
    try:
        uname = await state.get_data()
        if uname.get('username') == None:
            await state.update_data(username=message.text)
        else:
            await state.update_data(username=uname.get('username'))
        await LoginStatus.next()
        await message.answer("Теперь введите пароль: ")
    except Exception as e:
        print(e)
        await message.answer("Ошибка на сервере")

@dp.message_handler(state=LoginStatus.waiting_password)
async def login_password(message: types.Message, state: FSMContext):
    try:
        username = await state.get_data()
        req = rq.get("https://safefin-test.herokuapp.com/login?username=" + username['username'] + "&pwd=" + pwd256(message.text))
        if req.text == "OK":
            cur = conn.cursor()
            cur.execute("INSERT INTO users VALUES ('" + message.from_user.username + "', '" + username['username'] + "', '" + pwd256(message.text) + "');")
            key = types.ReplyKeyboardMarkup()
            key.add(types.KeyboardButton(text="Запустить приложение"))
            await message.answer("Вы успешно вошли в свой аккаунт!", reply_markup=key)
            await state.finish()
            cur.close()
            conn.commit()
        else:
            mark = types.InlineKeyboardMarkup()
            mark.add(types.InlineKeyboardButton(text="Войти снова", callback_data="login_button"))
            await message.answer("К сожалению данные не верные, попробуйте снова", reply_markup=mark)
            await state.finish()
    except Exception as e:
        print(e)
        await message.answer("Ошибка на сервере")

@dp.message_handler(commands="login")
async def login_handler(message: types.Message):
    try:
        cur = conn.cursor()
        cur.execute("SELECT username FROM users WHERE tg_username='" + message.from_user.username + "';")
        fetc = cur.fetchone()
        if fetc == None:
            keyb = types.ReplyKeyboardMarkup()
            keyb.add(kb("Отмена"))
            await message.answer("Для входа введите имя пользователя: ", keyb)
            await LoginStatus.waiting_username.set()
        else:
            keyb = types.InlineKeyboardMarkup()
            keyb.add(types.InlineKeyboardButton(text="Привязать новый", callback_data="newlog"))
            await message.answer("К вашему аккаунту уже привязан аккаунт " + fetc[0], reply_markup=keyb)
    except Exception as e:
        print(e)
        await message.answer("Ошибка на сервере")

@dp.callback_query_handler(text="reg_button")
async def reg_button(call: types.CallbackQuery):
    try:
        keyb = types.ReplyKeyboardMarkup()
        keyb.add(kb("Отмена"))
        await call.message.answer("Введите имя пользователя: ", reply_markup=keyb)
        await RegStatus.wait_user.set()
    except Exception as e:
        print(e)
        await call.message.answer("Ошибка на сервере")

@dp.message_handler(state=RegStatus.wait_user)
async def reg_username(message: types.Message, state: FSMContext):
    try:
        if validate_username(message.text) == None:
            await state.update_data(username=message.text)
            await RegStatus.next()
            await message.answer("Теперь введите пароль: ")
        else:
            await message.answer(validate_username(message.text))
    except Exception as e:
        print(e)
        await message.answer("Ошибка на сервере")

@dp.message_handler(state=RegStatus.wait_pass)
async def reg_pwd(message: types.Message, state: FSMContext):
    try:
        if validate_password(message.text) == None:
            username = await state.get_data()
            req = rq.get("https://safefin-test.herokuapp.com/register?username=" + username['username'] + "&pwd=" + pwd256(message.text))
            if req.text == "OK":
                cur = conn.cursor()
                cur.execute("DELETE FROM users WHERE tg_username='"+message.from_user.username+"';")
                cur.execute("INSERT INTO users VALUES ('" + message.from_user.username + "', '" + username['username'] + "', '" + pwd256(message.text) + "');")
                key = types.ReplyKeyboardMarkup()
                key.add(types.KeyboardButton(text="Запустить приложение"))
                await message.answer("Вы успешно зарегистрировались и вошли в свой новый аккаунт!", reply_markup=key)
                await state.finish()
                cur.close()
                conn.commit()
            else:
                await message.answer("Во время регистрации произошла ошибка, попробуйте ещё несколько раз, если не поможет, сообщите <a href='https://t.me/ivankarmanow'>создателю</a>")
                await state.finish()
        else:
            await message.answer(validate_password(message.text))
    except Exception as e:
        print(e)
        await message.answer("Ошибка на сервере")
           
@dp.message_handler(commands="reg")
async def reg_handler(message: types.Message):
    try:
        keyb = types.ReplyKeyboardMarkup()
        keyb.add(kb("Отмена"))
        await call.message.answer("Введите имя пользователя: ", reply_markup=keyb)
        await RegStatus.wait_user.set()
    except Exception as e:
        print(e)
        await message.answer("Ошибка на сервере")

def validate_username(text):
    try:
        res = None
        sym = 'qwertyuiopasdfghjklzxcvbnmQWERTYUIOPASDFGHJKLZXCVBNM1234567890_'
        for i in text:
            if i not in sym:
                res = False
                return "Имя пользователя может состоять только из латинских заглавных и строчных букв, цифр и знака подчеркивания _!"
                break
        if text[0] in '1234567890_':
            res = False
            return "Имя пользователя может начинаться только с буквы!"
        cur = conn.cursor()
        cur.execute("SELECT username FROM users WHERE username='" + text + "';")
        if cur.fetchone() != None:
            res = False
            return "Пользователь с таким именем уже существует!"
        return res
    except Exception as e:
        print(e)

def numbers(pwd):
    z = 0
    for x in pwd:
        if x.isdigit():
            z += 1
    return z
 
def upper_case(pwd):
    z = 0
    for x in pwd:
        if x.isupper():
            z += 1
    return z
 
def lower_case(pwd):
    z = 0
    for x in pwd:
        if x.islower():
            z += 1
    return z
 
def other_symbols(pwd):
    count_numbers = numbers(pwd)
    count_upper = upper_case(pwd)
    count_lower = lower_case(pwd)
    new_len = count_numbers + count_upper + count_lower
    return new_len
 
def validate_password(pwd):
    pwd = str(pwd)
    if len(pwd) < 8:
        return "Пароль должен содержать не менее 8 символов"
    elif numbers(pwd) <= 0:
        return "Пароль должен содержать хотя бы одну цифру"
    elif upper_case(pwd) <= 0:
        return "Пароль должен содержать хотя бы одну заглавную букву"
    elif lower_case(pwd) <= 0:
        return "Пароль должен содержать хотя бы одну строчную букву"
    elif other_symbols(pwd) == len(pwd):
        return "Пароль должен содержать хотя бы один символ, не являющийся буквой или цифрой"
    else:
        return None

def is_allowed(msg: types.Message, username=None):
    try:
        if username == None:
            user = msg.from_user.username
        else:
            user = username
        cur = conn.cursor()
        cur.execute("SELECT username, password FROM users WHERE tg_username='" + user + "';")
        up = cur.fetchone()
        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton(text="Войти", callback_data="login_button"),
            types.InlineKeyboardButton(text="Зарегистрироваться", callback_data="reg_button")
        )
        if up == None:
            return [False, ["К вашему telegram-аккаунту не привязан не один аккаунт KeepYourMoney, войдите или зарегистрируйтесь чтобы продолжить", kb]]
        else:
            username = up[0]
            pwd = up[1]
            req = rq.get("https://safefin-test.herokuapp.com/login?username=" + username + "&pwd=" + pwd)
            if req.text == "OK":
                return [True, up]
            else:
                cur.execute("DELETE FROM users WHERE tg_username='" + username + "';")
                return [False, ["К вашему telegram-аккаунту не привязан не один аккаунт KeepYourMoney, войдите или зарегистрируйтесь чтобы продолжить", kb]]
    except Exception as e:
        print(e)

@dp.message_handler(Text("Запустить приложение", ignore_case=True))
@dp.message_handler(commands="launch")
@dp.message_handler(Text("меню", ignore_case=True))
async def launch_app(message: types.Message):
    try:
        acts = [
            kb(text="Расходы"),
            kb(text="Категории"),
            kb(text="Анализ"),
            kb(text="Добавить расход")
        ]
        keyb = types.ReplyKeyboardMarkup()
        keyb.add(*acts)
        await message.answer("Выберите действие:", reply_markup=keyb)
    except Exception as e:
        print(e)
        await message.answer("Ошибка на сервере")

@dp.callback_query_handler(text_startswith="del_exp_")
async def del_exp_handler(clbck: types.CallbackQuery):
    try:
        udata = is_allowed(msg=clbck.message, username=clbck.from_user.username)
        if udata[0]:
            exp_id = clbck.data[8:]
            req = rq.get("https://safefin-test.herokuapp.com/del_exp?username=" + udata[1][0] + "&pwd=" + udata[1][1] + "&id=" + exp_id)
            if req.text == 'OK':
                await clbck.message.delete()
            elif req.text == "AD":
                await clbck.message.answer("Доступ запрещён, попробуйте позже")
            elif req.text == "Error!":
                await msg.answer("Непредвиденная ошибка на сервере, попробуйте позже")
            else:
                print(req.text)
                await msg.answer("Непредвиденная ошибка")
        else:
            await clbck.message.answer(udata[1][0], reply_markup=udata[1][1])
    except Exception as e:
        print(e)
        await clbck.message.answer("Ошибка на сервере")

@dp.message_handler(Text("расходы", ignore_case=True))
async def expense_handler(msg: types.Message):
    try:
        udata = is_allowed(msg)
        if udata[0]:
            req = rq.get("https://safefin-test.herokuapp.com/exps?username=" + udata[1][0] + "&pwd=" + udata[1][1])
            names = [
                '<b>Расход:</b> ',
                '\n<b>Категория:</b> ',
                '\n<b>Сумма:</b> ',
                '\n<b>Время:</b> '
            ]
            if req.text not in "ADError!":
                data = json.loads(req.text)
                keyb = types.ReplyKeyboardMarkup()
                keyb.add(
                    kb(text="Добавить расход"),
                    kb(text="Предыдущие расходы"),
                    kb(text="Расходы категории"),
                    kb(text="Меню")
                )
                if len(data) == 0:
                    keyb = types.ReplyKeyboardMarkup()
                    keyb.add(kb("Добавить расход"), kb("Меню"))
                    await msg.answer("У вас ещё нет расходов, хотите добавить расход?", reply_markup=keyb)
                else:
                    await msg.answer("Последние 10 ваших расходов: ")
                    for i in data[:10]:
                        msg_text = ""
                        for j in range(4):
                            msg_text += names[j] + str(i[j])
                        ikbm = types.InlineKeyboardMarkup()
                        del_cb = "del_exp_"+str(i[4])
                        del_but = ikb(text="Удалить", callback_data=del_cb)
                        ikbm.add(del_but)
                        await msg.answer(msg_text, reply_markup=ikbm)
                    await msg.answer("Вы можете добавить расход или посмотреть следующие 10 расходов", reply_markup=keyb)
            elif req.text == "AD":
                await msg.answer("Доступ запрещён, попробуйте заново войти")
            elif req.text == "Error!":
                await msg.answer("Непредвиденная ошибка на сервере, попробуйте позже")
            else:
                print(req.text)
                await msg.answer("Непредвиденная ошибка")
        else:
            await msg.answer(udata[1][0], reply_markup=udata[1][1])
    except Exception as e:
        print(e)
        await msg.answer("Ошибка на сервере")

@dp.message_handler(Text("добавить расход", ignore_case=True))
async def add_exp_start(msg: types.Message):
    try:
        udata = is_allowed(msg)
        if udata[0]:
            req = rq.get("https://safefin-test.herokuapp.com/cats?username=" + udata[1][0] + "&pwd=" + udata[1][1])
            if req.text not in "ADError!":
                cat_buts = []
                data = json.loads(req.text)
                if len(data) == 0:
                    keyb = types.ReplyKeyboardMarkup()
                    keyb.add(kb("Добавить категорию"), kb("Меню"))
                    await msg.answer("У вас нет ни одной категории, хотите добавить?", reply_markup=keyb)
                else:
                    await AddExpStatus.cat.set()
                    for i in data:
                        cat_buts.append(ikb(text=i[0], callback_data="add_exp_cat_"+i[0]))
                    keyb = types.InlineKeyboardMarkup()
                    keyb.add(*cat_buts)
                    await msg.answer("Выберите категорию расхода: ", reply_markup=keyb)
            elif req.text == "AD":
                await msg.answer("Доступ запрещён, попробуйте заново войти")
            elif req.text == "Error!":
                await msg.answer("Непредвиденная ошибка на сервере, попробуйте позже")
            else:
                print(req.text)
                await msg.answer("Непредвиденная ошибка")
        else:
            await msg.answer(udata[1][0], reply_markup=udata[1][1])
    except Exception as e:
        print(e)
        await msg.answer("Ошибка на сервере")

@dp.callback_query_handler(state=AddExpStatus.cat)
async def add_exp_category(clbck: types.CallbackQuery, state: FSMContext):
    try:
        await state.update_data(category=clbck.data.split("_")[-1])
        keyb = types.ReplyKeyboardMarkup()
        keyb.add(kb("Отмена"))
        await clbck.message.answer("Введите название расхода: ", reply_markup=keyb)
        await AddExpStatus.next()
    except Exception as e:
        print(e)
        await clbck.message.answer("Ошибка на сервере")

@dp.message_handler(state=AddExpStatus.title)
async def add_exp_title(msg: types.Message, state: FSMContext):
    try:
        if msg.text.lower() == "отмена":
            await state.finish()
            await msg.answer("Отмена добавления расхода")
            await launch_app(msg)
            return
        elif len(msg.text) < 256:
            await state.update_data(title=msg.text)
            await msg.answer("Теперь введите сумму расхода")
            await AddExpStatus.next()
        else:
            await msg.answer("Ваше название слишком длинное, сохранятся только первые 255 символов")
            await state.update_data(title=msg.text[:255])
            await AddExpStatus.next()
    except Exception as e:
        print(e)
        await msg.answer("Ошибка на сервере")
    
@dp.message_handler(state=AddExpStatus.summa)
async def add_exp_finish(msg: types.Message, state: FSMContext):
    try:
        if msg.text.isdigit():
            await state.update_data(summa=msg.text)
            up = is_allowed(msg)[1]
            exp_data = await state.get_data()
            req = rq.get("https://safefin-test.herokuapp.com/add_exp?username="+up[0]+"&pwd="+up[1]+"&title="+exp_data['title']+"&category="+exp_data['category']+"&sum="+exp_data['summa'])
            if req.text == "OK":
                names = [
                '\n<b>Расход:</b> ',
                '\n<b>Категория:</b> ',
                '\n<b>Сумма:</b> ',
                '\n<b>Время:</b> '
                ]
                i = [
                    exp_data['title'],
                    exp_data['category'],
                    exp_data['summa'], 
                    str(dt.datetime.now())
                ]
                msg_text = ""
                for j in range(4):
                    msg_text += names[j] + str(i[j])
                await msg.answer("Расход успешно добавлен"+msg_text)
            else:
                await msg.answer("Данные неверные, попробуйте снова "+req.text)
            await state.finish()
            await launch_app(msg)
        else:
            await msg.answer("Сумма расхода должна быть числом! Попробуйте снова")
            await AddExpStatus.summa.set()
    except Exception as e:
        print(e)
        await msg.answer("Ошибка на сервере")

@dp.message_handler(Text("расходы категории", ignore_case=True))
async def last_exps(msg: types.Message):
    try:
        udata = is_allowed(msg)
        if udata[0]:
            req = rq.get("https://safefin-test.herokuapp.com/cats?username=" + udata[1][0] + "&pwd=" + udata[1][1])
            if req.text not in "ADError!":
                data = json.loads(req.text)
                cat_buts = []
                if len(data) == 0:
                    keyb = types.ReplyKeyboardMarkup()
                    keyb.add(kb("Добавить категорию"), kb("Меню"))
                    await msg.answer("У вас нет ни одной категории, хотите добавить?", reply_markup=keyb)
                else:
                    for i in data:
                        cat_buts.append(ikb(text=i[0], callback_data="exp_cat_"+i[0]))
                    keyb = types.InlineKeyboardMarkup()
                    keyb.add(*cat_buts)
                    await msg.answer("Выберите категорию расходов: ", reply_markup=keyb)
            elif req.text == "AD":
                await msg.answer("Доступ запрещён, попробуйте заново войти")
            elif req.text == "Error!":
                await msg.answer("Непредвиденная ошибка на сервере, попробуйте позже")
            else:
                print(req.text)
                await msg.answer("Непредвиденная ошибка")
        else:
            await msg.answer(udata[1][0], reply_markup=udata[1][1])
    except Exception as e:
        print(e)
        await msg.answer("Ошибка на сервере")

@dp.callback_query_handler(text_startswith="exp_cat_")
async def cat_exp_handler(clbck: types.CallbackQuery):
    try:
        udata = is_allowed(msg=clbck.message, username=clbck.from_user.username)
        if udata[0]:
            cat = clbck.data.split("_")[-1]
            print(cat)
            req = rq.get("https://safefin-test.herokuapp.com/exps?username=" + udata[1][0] + "&pwd=" + udata[1][1] + "&cat=" + cat)
            names = [
                '<b>Расход:</b> ',
                '\n<b>Сумма:</b> ',
                '\n<b>Время:</b> '
            ]
            if req.text not in "ADError!":
                data = json.loads(req.text)
                keyb = types.ReplyKeyboardMarkup()
                keyb.add(
                    kb(text="Добавить расход"),
                    kb(text="Предыдущие расходы"),
                    kb(text="Расходы категории"),
                    kb(text="Меню")
                )
                await clbck.message.answer("Последние 10 расходов в категории " + cat + ": ")
                for i in data[:10]:
                    msg_text = ""
                    for j in range(3):
                        msg_text += names[j] + str(i[j])
                    ikbm = types.InlineKeyboardMarkup()
                    del_cb = "del_exp_"+str(i[3])
                    del_but = ikb(text="Удалить", callback_data=del_cb)
                    ikbm.add(del_but)
                    await clbck.message.answer(msg_text, reply_markup=ikbm)
                await clbck.message.answer("Вы можете добавить расход или посмотреть следующие 10 расходов", reply_markup=keyb)
            elif req.text == "AD":
                await clbck.message.answer("Доступ запрещён, попробуйте заново войти")
            elif req.text == "Error!":
                await clbck.message.answer("Непредвиденная ошибка на сервере, попробуйте позже")
            else:
                print(req.text)
                await clbck.message.answer("Непредвиденная ошибка")
        else:
            await clbck.message.answer(udata[1][0], reply_markup=udata[1][1])
    except Exception as e:
        print(e)
        await clbck.message.answer("Ошибка на сервере")

@dp.message_handler(Text("категории", ignore_case=True))
async def category_handler(msg: types.Message):
    try:
        udata = is_allowed(msg)
        if udata[0]:
            req = rq.get("https://safefin-test.herokuapp.com/cats?username=" + udata[1][0] + "&pwd=" + udata[1][1])
            if req.text not in "ADError!":
                data = json.loads(req.text)
                for i in data:
                    ikbm = types.InlineKeyboardMarkup()
                    del_cb = "del_cat_"+str(i[0])
                    del_but = ikb(text="Удалить", callback_data=del_cb)
                    ikbm.add(del_but)
                    await msg.answer(i[0], reply_markup=ikbm)
                keyb = types.ReplyKeyboardMarkup()
                keyb.add(kb(text="Добавить категорию"), kb(text="Меню"))
                await msg.answer("Вы можете добавить категорию или удалить существующие", reply_markup=keyb)
            elif req.text == "AD":
                await msg.answer("Доступ запрещён, попробуйте заново войти")
            elif req.text == "Error!":
                await msg.answer("Непредвиденная ошибка на сервере, попробуйте позже")
            else:
                print(req.text)
                await msg.answer("Непредвиденная ошибка")
        else:
            await msg.answer(udata[1][0], reply_markup=udata[1][1])
    except Exception as e:
        print(e)
        await msg.answer("Ошибка на сервере")

@dp.callback_query_handler(text_startswith="del_cat_")
async def del_cat_hadler(clbck: types.CallbackQuery, state: FSMContext):
    try:
        udata = is_allowed(msg=clbck.message, username=clbck.from_user.username)
        if udata[0]:
            await DelCatStatus.rem.set()
            keyb = types.ReplyKeyboardMarkup()
            keyb.add(kb("Отмена"))
            await clbck.message.answer('Удаление категории приведёт к удалению всех расходов этой категории! Если вы уверены, что хотите удалить категорию, напишите "Да, я уверен!" в ответ на это сообщение', reply_markup=keyb)
            await state.update_data(cat_name=clbck.data[8:])
        else:
            await clbck.message.answer(udata[1][0], reply_markup=udata[1][1])
    except Exception as e:
        print(e)
        await clbck.message.answer("Ошибка на сервере")

@dp.message_handler(Text("Да, я уверен!", ignore_case=True), state=DelCatStatus.rem)
async def real_del_cat(msg: types.Message, state: FSMContext):
    try:
        udata = is_allowed(msg)
        if udata[0]:
            dat = await state.get_data()
            cat_name = dat['cat_name']
            req = rq.get("https://safefin-test.herokuapp.com/del_cat?username=" + udata[1][0] + "&pwd=" + udata[1][1] + "&category=" + cat_name)
            if req.text == "OK":
                await msg.answer("Категория " + cat_name + " и все принадлежащие ей расходы удалены")
            elif req.text == "AD":
                await msg.answer("Доступ запрещён, попробуйте заново войти")
            elif req.text == "Error!":
                await msg.answer("Непредвиденная ошибка на сервере, попробуйте позже")
            else:
                print(req.text)
                await msg.answer("Непредвиденная ошибка")
        else:
            await msg.answer(udata[1][0], reply_markup=udata[1][1])
        await state.finish()
    except Exception as e:
        print(e)
        await msg.answer("Ошибка на сервере")

@dp.message_handler(Text("добавить категорию", ignore_case=True))
async def add_cat_handler(msg: types.Message):
    try:
        udata = is_allowed(msg)
        if udata[0]:
            await AddCatStatus.cat_name.set()
            keyb = types.ReplyKeyboardMarkup()
            keyb.add(kb("Отмена"))
            await msg.answer("Введите название категории: ", reply_markup=keyb)
        else:
            await msg.answer(udata[1][0], reply_markup=udata[1][1])
    except Exception as e:
        print(e)
        await msg.answer("Ошибка на сервере")

@dp.message_handler(state=AddCatStatus.cat_name)
async def add_cat_finish(msg: types.Message, state: FSMContext):
    try:
        if len(msg.text) < 256:
            udata = is_allowed(msg)
            req = rq.get("https://safefin-test.herokuapp.com/add_cat?username="+udata[1][0]+"&pwd="+udata[1][1]+"&category="+msg.text)
            if req.text == "OK":
                await msg.answer("Категория "+msg.text+" успешно добавлена")
                await state.finish()
                await launch_app(msg)
            else:
                await msg.answer("Ошибка при добавлении категории, повторите позже")
        else:
            await msg.answer("Ваше название слишком длинное, сохранятся только первые 255 символов")
            udata = is_allowed(msg)
            req = rq.get("https://safefin-test.herokuapp.com/add_cat?username="+udata[1][0]+"&pwd="+udata[1][1]+"&category="+msg.text[:255])
            if req.text == "OK":
                await msg.answer("Категория "+msg.text[:255]+" успешно добавлена")
                await state.finish()
                await launch_app(msg)
            else:
                await msg.answer("Ошибка при добавлении категории, повторите позже")
                await state.finish()
    except Exception as e:
        print(e)
        await msg.answer("Ошибка на сервере")

@dp.message_handler(text="Отмена", state='*')
async def cancel(msg: types.Message, state: FSMContext):
    await state.finish()
    await msg.answer("Отмена действия")

@dp.message_handler(Text("анализ", ignore_case=True))
async def analyze_handler(msg: types.Message):
    keyb = types.ReplyKeyboardMarkup()
    keyb.add(
        kb("Все расходы"),
        kb("По категории"),
        kb("Меню")
    )
    await msg.answer("Вы можете проанализировать все свои расходы за месяц или только расходы конкретной категории", reply_markup=keyb)

@dp.message_handler(Text("все расходы", ignore_case=True))
async def allsum_handler(msg: types.Message):
    try:
        udata = is_allowed(msg)
        if udata[0]:
            req = rq.get("https://safefin-test.herokuapp.com/allsum?username="+udata[1][0]+"&pwd="+udata[1][1])
            if req.text not in "ADError!":
                data = json.loads(req.text)
                await msg.answer("Общая сумма ваших расходов за месяц составляет "+str(data['all']))
                msg_text = "Сумма расходов в каждой категории за месяц: "
                labels = []
                values = []
                for i in data['categories']:
                    msg_text += "\n<b>"+i[0]+" - </b>"+str(i[1])+" ({0:.1f}%)".format(float(i[1])/(float(data['all'])/100.0))
                    labels.append(i[0])
                    values.append(i[1])
                fig, ax = plt.subplots()
                plt.pie(values,labels=labels)
                plt.axis('equal')
                filename = '{0}-{1}.png'.format(udata[1][0], str(dt.datetime.now()))
                plt.savefig(filename)
                fig.clear()
                await msg.answer(msg_text)
                await msg.answer_photo(types.InputFile(filename))
                os.remove(filename)
            else:
                await msg.answer("Ошибка при анализе, попробуйте позже")
        else:
            await msg.answer(udata[1][0], reply_markup=udata[1][1])
    except Exception as e:
        print(e)
        await msg.answer("Ошибка на сервере")

@dp.message_handler(Text("по категории", ignore_case=True))
async def analyze_handler(msg: types.Message):
    try:
        udata = is_allowed(msg)
        if udata[0]:
            req = rq.get("https://safefin-test.herokuapp.com/cats?username=" + udata[1][0] + "&pwd=" + udata[1][1])
            if req.text not in "ADError!":
                data = json.loads(req.text)
                cat_buts = []
                if len(data) == 0:
                    keyb = types.ReplyKeyboardMarkup()
                    keyb.add(kb("Добавить категорию"), kb("Меню"))
                    await msg.answer("У вас нет ни одной категории, хотите добавить?", reply_markup=keyb)
                else:
                    for i in data:
                        cat_buts.append(ikb(text=i[0], callback_data="analyze_"+i[0]))
                    keyb = types.InlineKeyboardMarkup()
                    keyb.add(*cat_buts)
                    await msg.answer("Выберите категорию расходов: ", reply_markup=keyb)
            elif req.text == "AD":
                await msg.answer("Доступ запрещён, попробуйте заново войти")
            elif req.text == "Error!":
                await msg.answer("Непредвиденная ошибка на сервере, попробуйте позже")
            else:
                print(req.text)
                await msg.answer("Непредвиденная ошибка")
        else:
            await msg.answer(udata[1][0], reply_markup=udata[1][1])
    except Exception as e:
        print(e)
        await msg.answer("Ошибка на сервере")

@dp.callback_query_handler(text_startswith="analyze_")
async def analyze_finish(clbck: types.CallbackQuery):
    try:
        udata = is_allowed(msg=clbck.message, username=clbck.from_user.username)
        if udata[0]:
            req = rq.get("https://safefin-test.herokuapp.com/analyze?username="+udata[1][0]+"&pwd="+udata[1][1]+"&category="+clbck.data.split("_")[-1])
            if req.text not in "ADError!":
                data = json.loads(req.text)
                await clbck.message.answer("Сумма ваших расходов в категории "+clbck.data.split("_")[-1]+" за месяц составила "+str(data['cat']))
                msg_text = "Расходы в категории за месяц: "
                label = []
                value = []
                for i in data['titles']:
                    msg_text += "\n<b>"+i[0]+" - </b>"+str(i[1])+" ({0:.1f}%)".format(float(i[1])/(float(data['cat'])/100.0))
                    label.append(i[0])
                    value.append(i[1])
                fig, ax = plt.subplots()
                plt.pie(value,labels=label)
                plt.axis('equal')
                filename = '{0}-{1}-.png'.format(udata[1][0], str(dt.datetime.now()), clbck.data.split("_")[-1])
                plt.savefig(filename)
                fig.clear()
                await clbck.message.answer(msg_text)
                await clbck.message.answer_photo(types.InputFile(filename))
                os.remove(filename)
            else:
                await clbck.message.answer("Ошибка при анализе, попробуйте позже")
        else:
            await clbck.message.answer(udata[1][0], reply_markup=udata[1][1])
    except Exception as e:
        print(e)
        await clbck.message.answer("Ошибка на сервере")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=False)