import nextcord
from nextcord.ext import commands
from nextcord.ui import View, Button
import json
from dotenv import load_dotenv
import os
from nextcord import Embed, Colour
from datetime import datetime, timezone

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
QUEUE_CHANNEL_ID = 1184854010071613490  # канал с очередью
THREAD_CHANNEL_ID = 1083875631781138552  # канал для веток
DATA_FILE = "queue_message.json"

intents = nextcord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Списки для хранения участников
trainees = []  # стажеры
mentors = []   # наставники

class QueueView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.message = None

    async def update(self):
        if not self.message:
            return

        embed = Embed(
            title="📋 Панель очереди для стажеров и их наставников",
            description="• Кнопки «Я стажер» и «Я наставник» доступны только соответствующим ролям.\n"
                       "• «Взять стажёра» — забираете первого в очереди стажера.\n"
                       "• Автокик: заявки старше 3 часов удаляются автоматически.",
            colour=Colour.blue()
        )
        embed.add_field(name="👶 Стажеры", value="\n".join([f"<@{uid}>" for uid in trainees]) if trainees else "—", inline=True)
        embed.add_field(name="👮‍♂️ Наставники", value="\n".join([f"<@{uid}>" for uid in mentors]) if mentors else "—", inline=True)

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
        if not trainees:
            await interaction.response.send_message("Нет стажеров в очереди!", ephemeral=True)
            return

        mentor_id = interaction.user.id
        trainee_id = trainees.pop(0)  # Берём первого стажёра из списка

        # Получаем объект пользователя стажёра
        trainee_user = await bot.fetch_user(trainee_id)

        channel = bot.get_channel(THREAD_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("Канал для веток не найден!", ephemeral=True)
            return

        # Создаём ветку (thread)
        thread = await channel.create_thread(
            name=f"Наставник: {interaction.user.display_name} — Стажёр: {trainee_user.display_name}",
            type=nextcord.ChannelType.public_thread
        )

        await thread.send(
            f"👋 Наставник {interaction.user.mention} взял стажёра {trainee_user.mention}.\n"
            f"Общение продолжается здесь."
        )

        await interaction.response.send_message("Стажёр взят, ветка создана!", ephemeral=True)
        await self.update()

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
    print(f"Бот онлайн: {bot.user}")

    global trainees, mentors
    trainees, mentors = load_queue_data()

    channel = bot.get_channel(QUEUE_CHANNEL_ID)
    if not channel:
        print("❌ Канал очереди не найден")
        return

    view = QueueView()
    message_id = load_message_id()

    if message_id:
        try:
            message = await channel.fetch_message(message_id)
            view.message = message
            await message.edit(view=view)
            await view.update()
            print("✅ Использую существующее сообщение очереди")
            return
        except nextcord.NotFound:
            print("⚠️ Старое сообщение удалено")

    initial_embed = Embed(
        title="📋 Панель очереди для стажеров и их наставников",
        description="• Кнопки «Я стажер» и «Я наставник» доступны только соответствующим ролям.\n"
                   "• «Взять стажёра» — откроет меню выбора конкретного стажёра.\n"
                   "• Автокик: заявки старше 3 часов удаляются автоматически.",
        colour=Colour.blue()
    )
    initial_embed.add_field(name="🎓 Стажеры", value="—", inline=True)
    initial_embed.add_field(name="🏫 Наставники", value="—", inline=True)

    message = await channel.send(content="", embed=initial_embed, view=view)
    view.message = message
    save_message_id(message.id)
    save_queue_data()
    print("🆕 Создано новое сообщение очереди")

@bot.event
async def on_message(message):
    # Логика автокика (удаление заявок старше 3 часов)
    from datetime import datetime  # Импорт datetime внутри функции или в начале файла
    now = datetime.now(timezone.utc)  # Сохраняем результат в переменную now
    for user_id in trainees[:]:
        # Здесь нужно добавить логику отслеживания времени добавления в очередь
        # Например, хранить время добавления в отдельном словаре
        pass
    for user_id in mentors[:]:
        # Аналогично для наставников
        pass

def save_message_id(message_id):
    with open(DATA_FILE, "w") as f:
        json.dump({"message_id": message_id}, f)

def load_message_id():
    if not os.path.exists(DATA_FILE):
        return None
    with open(DATA_FILE, "r") as f:
        return json.load(f).get("message_id")

@bot.event
async def on_ready():
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
                   "• «Взять стажёра» — откроет меню выбора конкретного стажёра.\n"
                   "• Автокик: заявки старше 3 часов удаляются автоматически.",
        colour=Colour.blue()
    )
    initial_embed.add_field(name="🎓 Стажеры", value="—", inline=True)
    initial_embed.add_field(name="🏫 Наставники", value="—", inline=True)

    message = await channel.send(embed=initial_embed, view=view)
    view.message = message
    save_message_id(message.id)
    save_queue_data()
    print("🆕 Создано новое сообщение очереди")


bot.run(TOKEN)
