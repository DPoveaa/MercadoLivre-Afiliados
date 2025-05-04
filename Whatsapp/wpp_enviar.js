const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const fetch = require('node-fetch').default;
const mime = require('mime-types');

const [,, legenda, nomeGrupo, imageUrl] = process.argv;

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: './auth_data' }),
    puppeteer: {
        headless: false,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

client.on('authenticated', () => {
    console.log('[AUTH] Autenticado com sucesso');
});

client.on('auth_failure', msg => {
    console.error('[AUTH ERROR]', msg);
});

client.on('ready', async () => {
    try {
        console.log('[READY] Cliente pronto!');
        const chats = await client.getChats();
        const grupo = chats.find(chat =>
            chat.isGroup &&
            chat.name.toLowerCase().trim() === nomeGrupo.toLowerCase().trim()
        );

        if (!grupo) throw new Error(`Grupo "${nomeGrupo}" não encontrado`);

        const chat = await client.getChatById(grupo.id._serialized);

        if (imageUrl) {
            try {
                const res = await fetch(imageUrl);
                if (!res.ok) throw new Error(`Falha ao buscar imagem (${res.status})`);

                const buffer = await res.buffer();
                const media = new MessageMedia(
                    res.headers.get('content-type') || mime.lookup(imageUrl),
                    buffer.toString('base64'),
                    'promocao.jpg'
                );
                await chat.sendMessage(media, { caption: legenda });
            } catch (imgErr) {
                console.error('Erro ao enviar imagem:', imgErr.message);
                await chat.sendMessage(legenda); // fallback para texto
            }
        } else {
            await chat.sendMessage(legenda);
        }

        console.log('Mensagem enviada com sucesso!');
    } catch (error) {
        console.error('Erro:', error.message);
    } finally {
        setTimeout(() => client.destroy(), 2000);
    }
});

client.initialize();
