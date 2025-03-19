# Vrok Telegram Bot

Vrok is a humorous AI assistant integrated with Telegram, powered by the Kobold API. It supports natural language conversations, context management, and translations between Russian and English.

## Features
- Interactive chat with a customizable AI character (default: Vrok).
- Context persistence across messages.
- Optional translation of user queries (RU -> EN) and AI responses (EN -> RU).
- Customizable response length with `мдXXX`, `mlXXX`, or `mdXXX` (e.g., `мд300` for 300 tokens, max 512).
- Detailed logging for debugging and development.

### 1. Install dependencies:
pip install -r requirements.txt

### 2. Configure the bot:
Rename config.json.example to config.json.
Edit config.json with your Telegram bot token and Kobold API URL.

### 3. Run the bot:
python main.py

Requirements
Python 3.8+

Kobold API server running locally or remotely.

### 4. Usage
#### 4.1 In Russian:
```plaintext
Список команд бота:
- /start Запускает бота и отправляет приветственное сообщение. Инициализирует контекст разговора с системным промптом.
- /help Показывает это сообщение со списком всех доступных команд.
- /clear Очищает текущий контекст разговора, позволяя начать общение с чистого листа.
- /continue Продолжает текущую историю без нового ввода, основываясь на сохранённом контексте.
- /usertranslate Включает или выключает перевод ваших текстовых сообщений на английский перед отправкой ИИ. По умолчанию включён.
- /aitranslate Включает или выключает перевод ответов ИИ на русский. По умолчанию включён.
- /memory [текст] Задаёт или показывает инструкцию (memory) о поведении ИИ. Без аргумента выводит текущее значение. Пример: /memory You are a friendly assistant — задаёт новое поведение.
- /character [имя] Задаёт или показывает имя персонажа ИИ (по умолчанию "Vrok"). Если перевод включён, имя переводится на английский. Пример: /character Alex — устанавливает имя "Alex".
- /usercharacter [имя] Задаёт или показывает ваше имя в диалоге (по умолчанию "User"). Добавляет ": " автоматически. Если перевод включён, имя переводится на английский. Пример: /usercharacter Анна — устанавливает "Anna: ".
- /getcontext Отправляет текущий контекст разговора и memory в виде текстового файла (без системного промпта).
- /extension [имя] Выбирает дополнение персонажа, влияющее на стиль общения. Без аргумента показывает список доступных дополнений (например, Humor, Wisdom, Sarcasm) и текущее активное. Пример: /extension Humor — активирует режим с юмором и остроумием.
- Голосовые сообщения Отправьте голосовое сообщение, и бот преобразует его в текст с помощью утилиты, покажет распознанный текст, а затем сгенерирует ответ ИИ с учётом текущего дополнения.
- Текстовые сообщения Отправьте текст, и бот ответит с учётом контекста, настроек перевода и выбранного дополнения. Используйте "..." для продолжения без ввода.In English:
```
#### 4.2 In English:
```plaintext
List of bot commands:
- /start Starts the bot and sends a welcome message. Initializes the conversation context with a system prompt.
- /help Shows this message with a list of all available commands.
- /clear Clears the current conversation context, allowing you to start fresh.
- /continue Continues the current story without new input, based on the saved context.
- /usertranslate Enables or disables translation of your text messages to English before sending to the AI. Enabled by default.
- /aitranslate Enables or disables translation of AI responses to Russian. Enabled by default.
- /memory [text] Sets or shows the instruction (memory) for the AI's behavior. Without an argument, it displays the current value. Example: /memory You are a friendly assistant — sets new behavior.
- /character [name] Sets or shows the AI character's name (default is "Vrok"). If translation is enabled, the name is translated to English. Example: /character Alex — sets the name "Alex".
- /usercharacter [name] Sets or shows your name in the dialogue (default is "User"). Automatically adds ": ". If translation is enabled, the name is translated to English. Example: /usercharacter Anna — sets "Anna: ".
- /getcontext Sends the current conversation context and memory as a text file (without the system prompt).
- /extension [name] Selects a character extension that affects the communication style. Without an argument, it shows the list of available extensions (e.g., Humor, Wisdom, Sarcasm) and the current active one. Example: /extension Humor — activates a mode with humor and wit.
- Voice messages Send a voice message, and the bot will convert it to text using a utility, display the recognized text, and then generate an AI response based on the current extension.
- Text messages Send a text message, and the bot will respond based on the context, translation settings, and selected extension. Use "..." to continue without new input.```

### 5. `LICENSE`

License
This project is licensed under the Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0). See the LICENSE file for details.
Contributing
Feel free to fork this repository and submit pull requests. For major changes, please open an issue first.
Author
Vitug (replace with your GitHub username or contact info)

```plaintext
Creative Commons Attribution-NonCommercial 4.0 International License
(CC BY-NC 4.0)

Attribution-NonCommercial 4.0 International

=======================================================================

By exercising the Licensed Rights (defined below), You accept and agree to be bound by the terms and conditions of this Creative Commons Attribution-NonCommercial 4.0 International Public License ("Public License"). To the extent this Public License may be interpreted as a contract, You are granted the Licensed Rights in consideration of Your acceptance of these terms and conditions, and the Licensor grants You such rights in consideration of benefits the Licensor receives from making the Licensed Material available under these terms and conditions.

Section 1 – Definitions.

a. Adapted Material means material subject to Copyright and Similar Rights that is derived from or based upon the Licensed Material and in which the Licensed Material is translated, altered, arranged, transformed, or otherwise modified in a manner requiring permission under the Copyright and Similar Rights held by the Licensor. For purposes of this Public License, where the Licensed Material is a musical work, performance, or sound recording, Adapted Material includes any synchronization of the Licensed Material with a moving image.

b. Copyright and Similar Rights means copyright and/or similar rights closely related to copyright including, without limitation, performance, broadcast, sound recording, and Sui Generis Database Rights, without regard to how the rights are labeled or categorized. For purposes of this Public License, the rights specified in Section 2(b)(1)-(2) are not Copyright and Similar Rights.

c. Effective Technological Measures means those measures that, in the absence of proper authority, may not be circumvented under laws fulfilling obligations under Article 11 of the WIPO Copyright Treaty adopted on December 20, 1996, and/or similar international agreements.

d. Exceptions and Limitations means fair use, fair dealing, and/or any other exception or limitation to Copyright and Similar Rights that applies to Your use of the Licensed Material.

e. Licensed Material means the artistic or literary work, database, or other material to which the Licensor applied this Public License.

f. Licensed Rights means the rights granted to You subject to the terms and conditions of this Public License, which are limited to all Copyright and Similar Rights that apply to Your use of the Licensed Material and that the Licensor has authority to license.

g. Licensor means the individual(s) or entity(ies) granting rights under this Public License.

h. NonCommercial means not primarily intended for or directed towards commercial advantage or monetary compensation. For purposes of this Public License, the exchange of the Licensed Material for other material subject to Copyright and Similar Rights by digital file-sharing or similar means is NonCommercial provided there is no payment of monetary compensation in connection with the exchange.

i. Share means to provide material to the public by any means or process that requires permission under the Licensed Rights, such as reproduction, public display, public performance, distribution, dissemination, communication, or importation, and to make material available to the public including in ways that members of the public may access the material from a place and at a time individually chosen by them.

j. Sui Generis Database Rights means rights other than copyright resulting from Directive 96/9/EC of the European Parliament and of the Council of 11 March 1996 on the legal protection of databases, as amended and/or succeeded, as well as other essentially equivalent rights anywhere in the world.

k. You means the individual or entity exercising the Licensed Rights under this Public License. Your has a corresponding meaning.

Section 2 – Scope.

a. License grant.

     1. Subject to the terms and conditions of this Public License, the Licensor hereby grants You a worldwide, royalty-free, non-sublicensable, non-exclusive, irrevocable license to exercise the Licensed Rights in the Licensed Material to:
          a. reproduce and Share the Licensed Material, in whole or in part, for NonCommercial purposes only; and
          b. produce and reproduce, but not Share, Adapted Material for NonCommercial purposes only.

     2. Exceptions and Limitations. For the avoidance of doubt, where Exceptions and Limitations apply to Your use, this Public License does not apply, and You do not need to comply with its terms and conditions.

     3. Term. The term of this Public License is specified in Section 6(a).

     4. Media and formats; technical modifications allowed. The Licensor authorizes You to exercise the Licensed Rights in all media and formats whether now known or hereafter created, and to make technical modifications necessary to do so. The Licensor waives and/or agrees not to assert any right or authority to forbid You from making technical modifications necessary to exercise the Licensed Rights, including technical modifications necessary to circumvent Effective Technological Measures. For purposes of this Public License, simply making modifications authorized by this Section 2(a)(4) never produces Adapted Material.

     5. Downstream recipients.
          a. Offer from the Licensor – Licensed Material. Every recipient of the Licensed Material automatically receives an offer from the Licensor to exercise the Licensed Rights under the terms and conditions of this Public License.
          b. No downstream restrictions. You may not offer or impose any additional or different terms or conditions on, or apply any Effective Technological Measures to, the Licensed Material if doing so restricts exercise of the Licensed Rights by any recipient of the Licensed Material.

     6. No endorsement. Nothing in this Public License constitutes or may be construed as permission to assert or imply that You are, or that Your use of the Licensed Material is, connected with, or sponsored, endorsed, or granted official status by, the Licensor or others designated to receive attribution as provided in Section 3(a)(1)(A)(i).

b. Other rights.

     1. Moral rights, such as the right of integrity, are not licensed under this Public License, nor are publicity, privacy, and/or other similar personality rights; however, to the extent possible, the Licensor waives and/or agrees not to assert any such rights held by the Licensor to the limited extent necessary to allow You to exercise the Licensed Rights, but not otherwise.

     2. Patent and trademark rights are not licensed under this Public License.

     3. To the extent possible, the Licensor waives any right to collect royalties from You for the exercise of the Licensed Rights, whether directly or through a collecting society under any voluntary or waivable statutory or compulsory licensing scheme. In all other cases the Licensor expressly reserves any right to collect such royalties, including when the Licensed Material is used other than for NonCommercial purposes.

Section 3 – License Conditions.

Your exercise of the Licensed Rights is expressly made subject to the following conditions.

a. Attribution.

     1. If You Share the Licensed Material, You must:
          a. retain the following if it is supplied by the Licensor with the Licensed Material:
               i. identification of the creator(s) of the Licensed Material and any others designated to receive attribution, in any reasonable manner requested by the Licensor (including by pseudonym if designated);
              ii. a copyright notice;
             iii. a notice that refers to this Public License;
              iv. a notice that refers to the disclaimer of warranties;
               v. a URI or hyperlink to the Licensed Material to the extent reasonably practicable;
          b. indicate if You modified the Licensed Material and retain an indication of any previous modifications; and
          c. indicate the Licensed Material is licensed under this Public License, and include the text of, or the URI or hyperlink to, this Public License.

     2. You may satisfy the conditions in Section 3(a)(1) in any reasonable manner based on the medium, means, and context in which You Share the Licensed Material. For example, it may be reasonable to satisfy the conditions by providing a URI or hyperlink to a resource that includes the required information.

     3. If requested by the Licensor, You must, to the extent reasonably practicable, remove any of the information required by Section 3(a)(1)(A) to the extent reasonably practicable.

Section 4 – Sui Generis Database Rights.

Where the Licensed Rights include Sui Generis Database Rights that apply to Your use of the Licensed Material:

a. for the avoidance of doubt, Section 2(a)(1) grants You the right to extract, reuse, reproduce, and Share all or a substantial portion of the contents of the database for NonCommercial purposes only and provided You do not Share Adapted Material;

b. if You include all or a substantial portion of the database contents in a database in which You have Sui Generis Database Rights, then the database in which You have Sui Generis Database Rights (but not its individual contents) is Adapted Material; and

c. You must comply with the conditions in Section 3(a) if You Share all or a substantial portion of the contents of the database.

For the avoidance of doubt, this Section 4 supplements and does not replace Your obligations under this Public License where the Licensed Rights include other Copyright and Similar Rights.

Section 5 – Disclaimer of Warranties and Limitation of Liability.

a. Unless otherwise separately undertaken by the Licensor, to the extent possible, the Licensor offers the Licensed Material as-is and as-available, and makes no representations or warranties of any kind concerning the Licensed Material, whether express, implied, statutory, or other. This includes, without limitation, warranties of title, merchantability, fitness for a particular purpose, non-infringement, absence of latent or other defects, accuracy, or the presence or absence of errors, whether or not known or discoverable. Where disclaimers of warranties are not allowed in full or in part, this disclaimer may not apply to You.

b. To the extent possible, in no event will the Licensor be liable to You on any legal theory (including, without limitation, negligence) or otherwise for any direct, special, indirect, incidental, consequential, punitive, exemplary, or other losses, costs, expenses, or damages arising out of this Public License or use of the Licensed Material, even if the Licensor has been advised of the possibility of such losses, costs, expenses, or damages. Where a limitation of liability is not allowed in full or in part, this limitation may not apply to You.

c. The disclaimer of warranties and limitation of liability provided above shall be interpreted in a manner that, to the extent possible, most closely approximates an absolute disclaimer and waiver of all liability.

Section 6 – Term and Termination.

a. This Public License applies for the term of the Copyright and Similar Rights licensed here. However, if You fail to comply with this Public License, then Your rights under this Public License terminate automatically.

b. Where Your right to use the Licensed Material has terminated under Section 6(a), it reinstates:
     1. automatically as of the date the violation is cured, provided it is cured within 30 days of Your discovery of the violation; or
     2. upon express reinstatement by the Licensor.

c. For the avoidance of doubt, this Section 6(b) does not affect any right the Licensor may have to seek remedies for Your violations of this Public License.

d. For the avoidance of doubt, the Licensor may also offer the Licensed Material under separate terms or conditions or stop distributing the Licensed Material at any time; however, doing so will not terminate this Public License.

e. Sections 1, 5, 6, 7, and 8 survive termination of this Public License.

Section 7 – Other Terms and Conditions.

a. The Licensor shall not be bound by any additional or different terms or conditions communicated by You unless expressly agreed.

b. Any arrangements, understandings, or agreements regarding the Licensed Material not stated herein are separate from and independent of the terms and conditions of this Public License.

Section 8 – Interpretation.

a. For the avoidance of doubt, this Public License does not, and shall not be interpreted to, reduce, limit, restrict, or impose conditions on any use of the Licensed Material that could lawfully be made without permission under this Public License.

b. To the extent possible, if any provision of this Public License is deemed unenforceable, it shall be automatically reformed to the minimum extent necessary to make it enforceable. If the provision cannot be reformed, it shall be severed from this Public License without affecting the enforceability of the remaining terms and conditions.

c. No term or condition of this Public License will be waived and no failure to comply consented to unless expressly agreed to by the Licensor.

d. Nothing in this Public License constitutes or may be interpreted as a limitation upon, or waiver of, any privileges and immunities that apply to the Licensor or You, including from the legal processes of any jurisdiction or authority.

=======================================================================

Creative Commons is not a party to its public licenses. Notwithstanding, Creative Commons may elect to apply one of its public licenses to material it publishes and in those instances will be considered the “Licensor.” The text of the Creative Commons public licenses is dedicated to the public domain under the CC0 Public Domain Dedication. Except for the limited purpose of indicating that material is licensed under a Creative Commons public license or as otherwise permitted by the Creative Commons policies published at creativecommons.org/policies, Creative Commons does not authorize the use of the trademark "Creative Commons" or any other trademark or logo of Creative Commons without its prior written consent including, without limitation, in connection with any unauthorized modifications to any of its public licenses or any other arrangements, understandings, or agreements concerning use of licensed material. For the avoidance of doubt, this paragraph does not form part of the public licenses.

Creative Commons may be contacted at creativecommons.org.
```

