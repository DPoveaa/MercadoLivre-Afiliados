// listar_chats.js
const { Client, LocalAuth } = require('whatsapp-web.js');

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: false
    }
});

client.on('ready', async () => {
    const chats = await client.getChats();
    chats.forEach(chat => {
        console.log(`NOME: ${chat.name} | ID: ${chat.id._serialized}`);
    });
    await client.destroy();
    process.exit(0);
});

client.initialize();
