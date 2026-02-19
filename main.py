import nextcord
from nextcord.ext import commands
from nextcord.ui import View, Button
import json
from dotenv import load_dotenv
import os
from nextcord import Embed, Colour, SelectOption
from datetime import datetime, timedelta

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
QUEUE_CHANNEL_ID = 1184854010071613490  # канал с очередью
THREAD_CHANNEL_ID = 1083875631781138552  # канал для веток
DATA_FILE = "queue_message.json"

intents = nextcord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
bot_started = False

# Списки для хранения участников
trainees = []  # стажеры
mentors = []  # наставники

class TraineeSelect(nextcord.ui.Select):
    def __init__(self, options, queue_view):
        super().__init__(
            placeholder="Выберите стажёра из очереди...",
            min_values=1,
            max_values=1,
            options=options
        )
        self.queue_view = queue_view  # Сохраняем ссылку на QueueView


    @classmethod
    async def create(cls, trainees_list, queue_view):
        options = []
        for trainee_id in trainees_list:
            try:
                user = bot.get_user(trainee_id) or await bot.fetch_user(trainee_id)
                option = nextcord.SelectOption(
                    label=user.display_name,
            value=str(trainee_id),
            description=f"ID: {trainee_id}"
        )
                options.append(option)
            except Exception as e:
                print(f"Ошибка загрузки пользователя {trainee_id}: {e}")
                option = nextcord.SelectOption(
            label="Неизвестный пользователь",
            value=str(trainee_id),
            description=f"ID: {trainee_id}"
        )
                options.append(option)

        if not options:
            options.append(
                nextcord.SelectOption(
            label="Нет доступных стажёров",
            value="no_trainees",
            description="В очереди нет стажёров"
        )
            )

        return cls(options, queue_view)  # Передаём queue_view в конструктор

    async def callback(self, interaction: nextcord.Interaction):
        if self.values == "no_trainees":
            await interaction.response.send_message("В очереди нет стажёров.", ephemeral=True)
            return

        # Исправленная строка — берём первый элемент списка
        selected_trainee_id = int(self.values[0])
        mentor_id = interaction.user.id

        # Дальнейший код без изменений...
        if selected_trainee_id in trainees:
            trainees.remove(selected_trainee_id)

        try:
            trainee_user = await bot.fetch_user(selected_trainee_id)
        except:
            await interaction.response.send_message("Ошибка: не удалось найти выбранного стажёра.", ephemeral=True)
            return

        channel = bot.get_channel(THREAD_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("Канал для веток не найден!", ephemeral=True)
            return

        thread = await channel.create_thread(
            name=f"Наставник: {interaction.user.display_name} — Стажёр: {trainee_user.display_name}",
            type=nextcord.ChannelType.public_thread
        )

        await thread.send(
            f"👋 Наставник {interaction.user.mention} взял стажёра {trainee_user.mention}.\n"
            f"Общение продолжается здесь."
        )

        await self.queue_view.update()  # Обновляем основное сообщение с очередью
        save_queue_data()

        await interaction.response.edit_message(
            content=f"Стажёр {trainee_user.display_name} взят ✅",
            view=None
        )


class QueueView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.message = None
        self.cooldowns = {}  # user_id: last_click_time
        self.COOLDOWN_SECONDS = 5  # Задержка 5 секунды
        self.active_dropdowns = set()  # Можно использовать для отслеживания активных меню
        self.trainee_already_selected = False  # Флаг: True — стажёр выбран, False — можно выбирать

    async def update(self):
        if not self.message:
            return

        embed = Embed(
            title="📋 Панель очереди для стажеров и их наставников",
            description="• Кнопки «Я стажер» и «Я наставник» доступны только соответствующим ролям.\n"
                        "• «Взять стажёра» — открывается список доступных стажёров.\n"
                        "• Автокик: заявки старше 3 часов удаляются автоматически.",
            colour=Colour.blue()
        )
        embed.add_field(name="👶 Стажеры", value="\n".join([f"<@{uid}>" for uid in trainees]) if trainees else "—",
                        inline=True)
        embed.add_field(name="👮‍♂️ Наставники", value="\n".join([f"<@{uid}>" for uid in mentors]) if mentors else "—",
                        inline=True)

        await self.message.edit(content="", embed=embed, view=self)

    async def try_match(self, channel):
        """Если есть и стажёр, и наставник — создаём ветку и удаляем их из очередей"""
        if not trainees or not mentors:
            return  # Нет пары — выходим

        # Берём первого стажёра и первого наставника
        trainee_id = trainees.pop(0)
        mentor_id = mentors.pop(0)

        # Получаем объекты пользователей
        try:
            trainee_user = await bot.fetch_user(trainee_id)
            mentor_user = await bot.fetch_user(mentor_id)
        except Exception as e:
            print(f"Ошибка при получении пользователя: {e}")
            return

        # Получаем канал для веток
        thread_channel = bot.get_channel(THREAD_CHANNEL_ID)
        if not thread_channel:
            print("Канал для веток не найден!")
            return

        # Создаём ветку
        thread = await thread_channel.create_thread(
            name=f"Наставник: {mentor_user.display_name} — Стажёр: {trainee_user.display_name}",
            type=nextcord.ChannelType.public_thread
        )

        # Отправляем приветственное сообщение
        await thread.send(
            f"👋 Автоматическое соединение!\n"
            f"Наставник {mentor_user.mention} и стажёр {trainee_user.mention}, общение продолжается здесь."
        )

        # Обновляем embed-сообщение очереди
        await self.update()

        # Лог в консоль
        print(f"Создана ветка: {mentor_user} ↔ {trainee_user}")

    @nextcord.ui.button(label="Я стажер", style=nextcord.ButtonStyle.green)
    async def trainee(self, button: Button, interaction: nextcord.Interaction):
        REQUIRED_ROLE_ID = 964079933863362570
        # Проверяем, есть ли у пользователя нужная роль
        role = interaction.guild.get_role(REQUIRED_ROLE_ID)
        if not role:
            await interaction.response.send_message("❌ Роль не найдена. Обратитесь к администратору.", ephemeral=True)
            return

        if role not in interaction.user.roles:
            await interaction.response.send_message(
                f"Вы не можете использовать эту кнопку — нужна роль {role.mention}.", ephemeral=True)
            return
        if interaction.user.id in trainees:
            await interaction.response.send_message("Вы уже в списке стажеров!", ephemeral=True)
            return
        trainees.append(interaction.user.id)
        await interaction.response.send_message("Вы добавлены в список стажеров.", ephemeral=True)
        await self.update()
        await self.try_match(interaction.channel)

    @nextcord.ui.button(label="Я наставник", style=nextcord.ButtonStyle.primary)
    async def mentor(self, button: Button, interaction: nextcord.Interaction):
        ROLE_ID_1 = 1174738465401884692
        ROLE_ID_2 = 1434215165678587914

        # Получаем роли из сервера
        role1 = interaction.guild.get_role(ROLE_ID_1)
        role2 = interaction.guild.get_role(ROLE_ID_2)

        if not role1 and not role2:
            await interaction.response.send_message("❌ Ошибка: роли не найдены. Обратитесь к администратору.",
                                                    ephemeral=True)
            return

        # Проверяем, есть ли у пользователя хотя бы одна из этих ролей
        has_role = False
        role_names = []

        if role1 and role1 in interaction.user.roles:
            has_role = True
            role_names.append(role1.name)

        if role2 and role2 in interaction.user.roles:
            has_role = True
            role_names.append(role2.name)

        if not has_role:
            allowed_roles = " или ".join([f"**{r.name}**" for r in [role1, role2] if r])
            await interaction.response.send_message(
                f"Вы не можете использовать эту кнопку — нужна роль: {allowed_roles}.",
                ephemeral=True
            )
            return
        if interaction.user.id in mentors:
            await interaction.response.send_message("Вы уже в списке наставников!", ephemeral=True)
            return
        mentors.append(interaction.user.id)
        await interaction.response.send_message("Вы добавлены в список наставников.", ephemeral=True)
        await self.update()
        await self.try_match(interaction.channel)

    @nextcord.ui.button(label="Взять стажёра", style=nextcord.ButtonStyle.secondary)
    async def take_trainee(self, button: Button, interaction: nextcord.Interaction):
        user_id = interaction.user.id
        now = datetime.now()

        # Проверяем cooldown
        if user_id in self.cooldowns:
            last_click = self.cooldowns[user_id]
            time_since_last = now - last_click

            if time_since_last < timedelta(seconds=self.COOLDOWN_SECONDS):
                remaining = self.COOLDOWN_SECONDS - time_since_last.total_seconds()
                await interaction.response.send_message(
                    f"❌ Подождите {remaining:.1f} секунд перед следующим использованием.",
                    ephemeral=True
                )
                return
        self.cooldowns[user_id] = now

        ROLE_ID_1 = 1174738465401884692
        ROLE_ID_2 = 1434215165678587914

        role1 = interaction.guild.get_role(ROLE_ID_1)
        role2 = interaction.guild.get_role(ROLE_ID_2)

        if not role1 and not role2:
            await interaction.response.send_message("❌ Ошибка: роли не найдены. Обратитесь к администратору.",
                                                    ephemeral=True)
            return

        has_role = False
        if role1 and role1 in interaction.user.roles:
            has_role = True
        if role2 and role2 in interaction.user.roles:
            has_role = True

        if not has_role:
            allowed_roles = " или ".join([f"**{r.name}**" for r in [role1, role2] if r])
            await interaction.response.send_message(
                f"Вы не можете использовать эту кнопку — нужна роль: {allowed_roles}.",
                ephemeral=True
            )
            return

        # Разрешаем выбор — устанавливаем флаг в True
        self.is_selection_active = True

        if not trainees:
            await interaction.response.send_message(
                "❌ Нет стажёров в очереди!\n",
                ephemeral=True
            )
            return

        # Создаём меню с опциями заранее (асинхронно)
        trainee_select = await TraineeSelect.create(trainees, self)
        select_view = nextcord.ui.View()
        select_view.add_item(trainee_select)

        await interaction.response.send_message(
            "Выберите стажёра из списка:",
            view=select_view,
            ephemeral=True
        )



    @nextcord.ui.button(label="Покинуть очередь", style=nextcord.ButtonStyle.secondary)
    async def leave_queue(self, button: Button, interaction: nextcord.Interaction):
        if interaction.user.id in trainees:
            trainees.remove(interaction.user.id)
            await interaction.response.send_message("Вы покинули список стажеров.", ephemeral=True)
        elif interaction.user.id in mentors:
            mentors.remove(interaction.user.id)
            await interaction.response.send_message("Вы покинули список наставников.", ephemeral=True)
        else:
            await interaction.response.send_message("Вы не находитесь в очереди.", ephemeral=True)
        await self.update()


def save_queue_data():
    with open(DATA_FILE, "w") as f:
        json.dump({"trainees": trainees, "mentors": mentors}, f)


def load_queue_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            return data["trainees"], data["mentors"]
    return [], []


@bot.event
async def on_ready():
    global bot_started

    if bot_started:
        return

    bot_started = True

    print(f"Бот онлайн: {bot.user}")

    global trainees, mentors
    trainees, mentors = load_queue_data()

    channel = bot.get_channel(QUEUE_CHANNEL_ID)
    if not channel:
        print("❌ Канал очереди не найден")
        return

    # Удаляем ВСЕ сообщения, отправленные ботом в канале очереди
    try:
        async for message in channel.history(limit=100):  # Проверяем последние 100 сообщений
            if message.author.id == bot.user.id:
                await message.delete()
                print(f"Удалено старое сообщение бота: {message.id}")
    except Exception as e:
        print(f"Ошибка при удалении сообщений: {e}")

    # Создаём новое сообщение с очередью
    view = QueueView()

    initial_embed = Embed(
        title="📋 Панель очереди для стажеров и их наставников",
        description="• Кнопки «Я стажер» и «Я наставник» доступны только соответствующим ролям.\n"
                    "• «Взять стажёра» — открывается список доступных стажёров.\n"
                    "• Автокик: заявки старше 3 часов удаляются автоматически.",
        colour=Colour.blue()
    )
    initial_embed.add_field(name="👶 Стажеры", value="—", inline=True)
    initial_embed.add_field(name="👮‍♂️ Наставники", value="—", inline=True)

    message = await channel.send(embed=initial_embed, view=view)
    view.message = message
    save_queue_data()
    print("🆕 Создано новое сообщение очереди")


bot.run(TOKEN)
