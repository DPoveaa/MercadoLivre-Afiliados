const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const fetch = require('node-fetch').default;
const mime = require('mime-types');

const [,, legenda, nomeGrupo, imageUrl] = process.argv;

console.log(`Procurando grupo com nome: "${nomeGrupo}"`);

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: './auth_data' }),
    puppeteer: {
        headless: true,
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
        console.log('[READY] Cliente pronto! Aguardando sincronização...');
        await new Promise(resolve => setTimeout(resolve, 3000)); // espera 3 segundos

        const chats = await client.getChats(); // isso costuma falhar se o WhatsApp ainda está sincronizando
        const grupo = chats.find(chat =>
            chat.isGroup &&
            chat.name.toLowerCase().includes(nomeGrupo.toLowerCase().trim())
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
        setTimeout(async () => {
            try {
                await client.destroy();
                console.log("Cliente encerrado com sucesso.");
            } catch (e) {
                console.error("Erro ao encerrar o cliente:", e.message);
            }
        }, 2000);
    }
    
});

process.on('uncaughtException', (err) => {
    console.error('❌ Uncaught Exception:', err);
    process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('❌ Unhandled Rejection:', reason);
    process.exit(1);
});


client.initialize();
