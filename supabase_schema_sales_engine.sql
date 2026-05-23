-- ============================================================
-- Ana Lead Tracker — Sales Engine Schema (Module 2)
-- Run this AFTER supabase_schema.sql in your Supabase SQL Editor
-- ============================================================
--
-- Adds the conversion machinery for turning scored leads into
-- paying Ana Receptionist clients. Based on the synthesized
-- methodology of Connor Murray (Oracle), Teddy Frank (UserGems),
-- Jason Bay (Outbound Squad), and Superhuman Prospecting (H2H).
--
-- Tuned for high-ticket consultative sales ($20k-$50k Ana deals),
-- not SaaS spray-and-pray.
-- ============================================================

-- 1. SALES_CALLS — every call attempt is logged here (granular)
-- This is separate from call_notes (which is for general notes).
-- This table powers the Conversion Metrics dashboard later.
create table if not exists sales_calls (
    id uuid default gen_random_uuid() primary key,
    business_id uuid not null references businesses(id) on delete cascade,
    caller text default 'josue' check (caller in ('josue', 'santiago')),
    call_started_at timestamptz default now(),
    call_ended_at timestamptz,
    duration_seconds integer,
    language text default 'en' check (language in ('en', 'es')),

    -- Outcome funnel
    connected boolean default false,
    reached_decision_maker boolean default false,
    conversation_quality_score integer check (conversation_quality_score between 1 and 10),
    framework_used text default '3-part-value' check (framework_used in ('3-part-value', '5cx5', 'custom')),

    outcome text check (outcome in (
        'demo_booked',
        'callback_requested',
        'voicemail_left',
        'gatekeeper_only',
        'no_answer',
        'not_interested',
        'wrong_number',
        'do_not_contact'
    )),

    -- Personalized opener used (snapshot — what Claude generated)
    opener_used text,

    -- Notes + follow-up
    notes text,
    next_action text,
    next_action_date date,

    -- Pipeline value (custom per deal since pricing varies $20k-$50k)
    estimated_deal_value numeric(10, 2),

    created_at timestamptz default now()
);

-- 2. OBJECTIONS — the bible of objections + handlers
-- Bilingual (EN/ES) for Phoenix market advantage.
-- Acknowledge → Reframe → Reclose pattern (Connor Murray framework).
create table if not exists objections (
    id uuid default gen_random_uuid() primary key,
    code text unique not null,  -- short slug, e.g., 'already_have_someone'

    -- The objection text (what the prospect says)
    objection_text_en text not null,
    objection_text_es text,

    category text check (category in (
        'price', 'timing', 'trust', 'competition',
        'fit', 'authority', 'fear', 'information'
    )),

    -- The 3-step handler (Connor Murray framework)
    acknowledge_en text not null,
    acknowledge_es text,
    reframe_en text not null,
    reframe_es text,
    reclose_en text not null,
    reclose_es text,

    -- Social proof to weave in (Ricardo Diaz Insurance references)
    social_proof_en text,
    social_proof_es text,

    -- Performance tracking
    times_used integer default 0,
    times_succeeded integer default 0,

    -- Soft delete
    archived boolean default false,

    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- 3. OBJECTION_ENCOUNTERS — which objections came up on which calls
-- Powers analytics: "Your dental opener gets the 'too expensive'
-- objection 80% of the time — try this reframe variant"
create table if not exists objection_encounters (
    id uuid default gen_random_uuid() primary key,
    call_id uuid not null references sales_calls(id) on delete cascade,
    objection_id uuid references objections(id) on delete set null,
    was_handled boolean default false,  -- did the prospect engage after the reframe?
    notes text,
    created_at timestamptz default now()
);

-- 4. INDEXES for fast Cockpit / Bible queries
create index if not exists idx_sales_calls_business on sales_calls(business_id);
create index if not exists idx_sales_calls_caller_date on sales_calls(caller, call_started_at desc);
create index if not exists idx_sales_calls_outcome on sales_calls(outcome);
create index if not exists idx_objections_category on objections(category);
create index if not exists idx_objections_code on objections(code);
create index if not exists idx_obj_encounters_call on objection_encounters(call_id);

-- 5. UPDATED_AT TRIGGER for objections
create trigger objections_updated_at
    before update on objections
    for each row execute function update_updated_at();

-- ============================================================
-- 6. PRE-SEEDED OBJECTIONS — the 10 you'll actually hear
-- selling Ana Receptionist to Phoenix SMBs ($20k-$50k tickets)
-- ============================================================

insert into objections (code, category, objection_text_en, objection_text_es,
    acknowledge_en, acknowledge_es,
    reframe_en, reframe_es,
    reclose_en, reclose_es,
    social_proof_en, social_proof_es) values

-- 1. "We already have a receptionist"
('already_have_someone',
 'competition',
 'We already have someone answering our phones.',
 'Ya tenemos a alguien contestando los teléfonos.',
 'That makes total sense — most successful businesses your size do. I''m not here to replace them.',
 'Tiene mucho sentido — los negocios exitosos como el suyo siempre los tienen. No estoy aquí para reemplazarlos.',
 'What I''m hearing from owners like Ricardo at Diaz Insurance is that their receptionists were great at handling calls during business hours — but they were losing 25-30% of calls outside hours, during lunch, or when multiple people called at once. Ana doesn''t replace your team. She covers the gap your team physically can''t cover.',
 'Lo que estoy escuchando de dueños como Ricardo en Diaz Insurance es que sus recepcionistas eran excelentes durante horas de oficina — pero estaban perdiendo 25-30% de llamadas fuera de hora, durante el almuerzo, o cuando llamaban varios a la vez. Ana no reemplaza a su equipo. Cubre el espacio que su equipo físicamente no puede cubrir.',
 'Worth seeing how it works for them? I have Wednesday at 10 or Thursday at 2.',
 '¿Le parece bien ver cómo les funciona? Tengo el miércoles a las 10 o el jueves a las 2.',
 'Ricardo Diaz Insurance: was missing ~15 calls/week before Ana. Now captures them all, books appointments after hours.',
 'Ricardo Diaz Insurance: perdía ~15 llamadas por semana antes de Ana. Ahora las captura todas, agenda citas fuera de hora.'),

-- 2. "Too expensive"
('too_expensive',
 'price',
 'That sounds expensive. Whats the cost?',
 '¿Eso suena caro. ¿Cuál es el precio?',
 'Fair question — I''d ask the same thing.',
 'Pregunta válida — yo preguntaría lo mismo.',
 'Most clients we work with think about it this way: one missed HVAC emergency call in Phoenix is a $400-$800 lost job. One missed dental new-patient call is $2,000-$5,000 in lifetime value. Ana pays for herself the moment she catches the calls your team misses. The investment ranges depending on call volume and complexity — but the math always works out within the first 60 days for businesses your size. I''d rather show you exactly what the ROI looks like for your specific call volume than throw a number out cold.',
 'La mayoría de nuestros clientes lo piensan así: una llamada de emergencia de HVAC perdida en Phoenix son $400-$800 en trabajo perdido. Una llamada de paciente nuevo dental perdida son $2,000-$5,000 de valor de por vida. Ana se paga sola en el momento que captura las llamadas que su equipo pierde. La inversión varía según volumen y complejidad — pero las matemáticas siempre funcionan dentro de los primeros 60 días para negocios de su tamaño. Prefiero mostrarle el ROI exacto para su volumen de llamadas en vez de tirar un número en frío.',
 'Let me show you the ROI math on a 15-minute call — Wednesday or Thursday work?',
 '¿Permítame mostrarle las matemáticas del ROI en una llamada de 15 minutos — el miércoles o el jueves le funciona?',
 'Ricardo Diaz Insurance recovered their full investment in the first 90 days through captured after-hours calls alone.',
 'Ricardo Diaz Insurance recuperó toda su inversión en los primeros 90 días solo a través de llamadas capturadas fuera de hora.'),

-- 3. "Customers won't trust talking to AI"
('customers_wont_trust_ai',
 'trust',
 'My customers wont want to talk to a robot.',
 'Mis clientes no van a querer hablar con un robot.',
 'I hear that a lot, and it''s a real concern — especially with older or Spanish-speaking customers.',
 'Eso lo escucho mucho, y es una preocupación real — especialmente con clientes mayores o que hablan español.',
 'Here''s what we''ve found: Ana doesn''t announce she''s AI. She sounds like a warm, professional receptionist who happens to be available 24/7 and speaks perfect Spanish. We''ve had clients run her for weeks before mentioning it to customers — and the feedback is usually "your receptionist is amazing." The reality is your customers are already talking to AI on Amazon, their bank, their doctor''s appointment system. The bar isn''t "no AI" — it''s "does it actually help them get what they need." Ana does.',
 'Esto es lo que hemos encontrado: Ana no anuncia que es IA. Suena como una recepcionista cálida y profesional que está disponible 24/7 y habla español perfecto. Hemos tenido clientes que la usan por semanas antes de mencionarlo a sus clientes — y la retroalimentación usualmente es "su recepcionista es increíble." La realidad es que sus clientes ya están hablando con IA en Amazon, su banco, el sistema de citas de su doctor. La barrera no es "sin IA" — es "¿realmente les ayuda a conseguir lo que necesitan?" Ana sí.',
 'Want to call our demo line and hear her yourself? Takes 2 minutes — I''ll text you the number.',
 '¿Quiere llamar a nuestra línea de demostración y escucharla usted mismo? Toma 2 minutos — le envío el número por mensaje.',
 'Ricardo Diaz Insurance: zero complaints from Spanish-speaking clients in 6+ months live.',
 'Ricardo Diaz Insurance: cero quejas de clientes hispanohablantes en más de 6 meses en vivo.'),

-- 4. "We don't get that many calls"
('dont_get_many_calls',
 'fit',
 'Honestly we don''t get that many calls.',
 'La verdad no recibimos tantas llamadas.',
 'Got it — that''s actually the smartest concern to raise. No point investing if the volume isn''t there.',
 'Entendido — es la preocupación más inteligente que puede tener. No tiene caso invertir si no hay el volumen.',
 'Here''s what most owners are surprised by though: when we do a free 7-day call audit, we consistently find businesses are getting 30-50% more calls than they thought — mostly going to voicemail, hanging up, or rolling to busy. The ones answering are visible. The ones that aren''t answering, you don''t see. Would you be open to letting us run the audit? Zero cost, zero commitment — we just connect to your phone records for a week and show you the actual numbers. If the volume isn''t there, we tell you straight up.',
 'Esto es lo que sorprende a la mayoría de los dueños: cuando hacemos una auditoría gratuita de 7 días, consistentemente encontramos que los negocios reciben 30-50% más llamadas de lo que pensaban — la mayoría yendo a buzón de voz, colgando, o sonando ocupado. Las que contestan, las ve. Las que no contestan, no las ve. ¿Estaría abierto a que hagamos la auditoría? Costo cero, compromiso cero — solo nos conectamos a sus registros telefónicos por una semana y le mostramos los números reales. Si no hay volumen, se lo decimos directamente.',
 'Should I set up the audit? Takes 5 minutes on your end.',
 '¿Quiere que armemos la auditoría? Toma 5 minutos de su parte.',
 'Two prospects this month thought they got 30 calls/week — audit showed 95 and 110 respectively.',
 'Dos prospectos este mes pensaban que recibían 30 llamadas/semana — la auditoría mostró 95 y 110 respectivamente.'),

-- 5. "Just send me information"
('send_me_info',
 'information',
 'Just send me some info and I''ll look at it.',
 'Mándeme información y la reviso.',
 'I will absolutely send you something — but I want to make sure I send the right thing.',
 'Por supuesto le envío algo — pero quiero asegurarme de enviarle lo correcto.',
 'A generic deck won''t answer your specific questions, and honestly you''ll skim it for 30 seconds and toss it. What works way better is a 15-minute call where I show you exactly how this works for [their industry] businesses in Phoenix — using your actual numbers. Then I send you a one-page summary tailored to what we discussed. Way more useful than reading a brochure cold.',
 'Una presentación genérica no va a contestar sus preguntas específicas, y honestamente la va a ojear 30 segundos y la tira. Lo que funciona muchísimo mejor es una llamada de 15 minutos donde le muestro exactamente cómo funciona esto para negocios de [su industria] en Phoenix — usando sus números reales. Luego le envío un resumen de una página personalizado a lo que discutimos. Mucho más útil que leer un folleto en frío.',
 'How''s Wednesday at 10 or Thursday at 2 for a quick 15?',
 '¿Le funciona el miércoles a las 10 o el jueves a las 2 para 15 minutos rápidos?',
 NULL, NULL),

-- 6. "I need to ask my partner / owner"
('need_to_ask_partner',
 'authority',
 'I need to talk to my partner before deciding anything.',
 'Necesito hablar con mi socio antes de decidir.',
 'Of course — a decision like this should involve everyone with skin in the game.',
 'Por supuesto — una decisión así debería involucrar a todos con algo en juego.',
 'Why don''t we set the demo with both of you in the room? 30 minutes, both of you ask whatever you want, and you can decide together right after. That''s way more efficient than me explaining it to you, you explaining it to them, and them having questions you can''t answer. What does their calendar usually look like in the mornings vs afternoons?',
 '¿Por qué no agendamos la demostración con los dos en la sala? 30 minutos, los dos preguntan lo que quieran, y deciden juntos justo después. Es mucho más eficiente que yo se lo explique a usted, usted se lo explique a ellos, y ellos tengan preguntas que usted no puede contestar. ¿Cómo es su calendario usualmente en las mañanas o en las tardes?',
 'Should we look at next week, Tuesday or Wednesday — pick whichever works for both of you?',
 '¿Vemos la próxima semana, martes o miércoles — el que funcione para los dos?',
 NULL, NULL),

-- 7. "How is this different from voicemail?"
('how_different_from_voicemail',
 'fit',
 'How is this any different from voicemail or our answering service?',
 '¿En qué es diferente esto del buzón de voz o de nuestro servicio de contestadora?',
 'That''s the right question — and honestly the answer is night-and-day.',
 'Esa es la pregunta correcta — y honestamente la diferencia es de día y noche.',
 'Voicemail captures intent but loses 70%+ of callers who hang up. Traditional answering services take messages and you call back — by then the customer already called your competitor. Ana actually has the conversation. She qualifies the call, books the appointment directly into your calendar, sends the customer a confirmation text, and only escalates to you what truly needs your attention. Your customer hangs up having gotten what they needed. You wake up to a booked schedule, not a voicemail backlog.',
 'El buzón de voz captura intención pero pierde 70%+ de los que cuelgan. Los servicios de contestadora tradicionales toman mensajes y usted devuelve la llamada — para entonces el cliente ya llamó a su competidor. Ana tiene la conversación. Califica la llamada, agenda la cita directamente en su calendario, envía un mensaje de confirmación al cliente, y solo le escala lo que verdaderamente necesita su atención. Su cliente cuelga habiendo conseguido lo que necesitaba. Usted se despierta con un calendario lleno, no una bandeja de buzones de voz.',
 'Want to see her actually book an appointment live on a demo? Wednesday or Thursday work?',
 '¿Quiere verla agendar una cita en vivo en una demostración? ¿Miércoles o jueves le funciona?',
 'Ricardo Diaz Insurance: 23% increase in booked appointments after replacing their answering service with Ana.',
 'Ricardo Diaz Insurance: 23% aumento en citas agendadas después de reemplazar su servicio de contestadora con Ana.'),

-- 8. "We tried something like this and it didn't work"
('tried_before_didnt_work',
 'trust',
 'We tried something like this before and it didn''t work.',
 'Ya intentamos algo así antes y no funcionó.',
 'I bet — I''ve heard that exact thing a dozen times. Tell me what you tried?',
 'Le creo — he escuchado eso una docena de veces. ¿Qué intentaron?',
 '[After they answer]: Got it — most of what people tried before was an IVR menu ("press 1 for sales") or a chatbot that could only answer pre-programmed FAQs. Ana is a different category — she''s actually conversational AI, she handles unpredictable questions, she speaks Spanish like a native, and she connects directly to your calendar to book appointments. The ones that failed were technology from 3-5 years ago. This is genuinely different and worth a fresh look, especially since you already have intuition for what went wrong last time.',
 '[Después que contesten]: Entendido — la mayoría de lo que las personas intentaron antes era un menú IVR ("oprima 1 para ventas") o un chatbot que solo contestaba preguntas pre-programadas. Ana es otra categoría — es IA conversacional real, maneja preguntas impredecibles, habla español como nativa, y se conecta directamente a su calendario para agendar citas. Las que fallaron eran tecnología de hace 3-5 años. Esto es genuinamente diferente y vale una mirada fresca, especialmente porque usted ya tiene intuición de qué falló la vez pasada.',
 'Worth 15 minutes to compare what you tried vs what Ana actually does?',
 '¿Vale 15 minutos comparar lo que intentaron vs lo que Ana realmente hace?',
 NULL, NULL),

-- 9. "We're not ready right now / call me back in X months"
('not_ready_call_later',
 'timing',
 'We''re not ready right now. Call me back in 6 months.',
 'No estamos listos en este momento. Llámeme en 6 meses.',
 'Totally fair — and I will absolutely follow up when you say.',
 'Totalmente justo — y le doy seguimiento exactamente cuando me diga.',
 'Just so I can call you with the right context — what changes between now and then? Is it a budget cycle, a hire you''re waiting on, a project wrapping up? The reason I ask is sometimes "6 months" really means "I don''t want to deal with this right now" — and other times it''s a real timing thing where I should have you set up to start in month 4 so you''re live by month 6. Want to help me understand?',
 'Solo para llamarle con el contexto correcto — ¿qué cambia entre ahora y entonces? ¿Es un ciclo de presupuesto, una contratación que esperan, un proyecto terminando? Le pregunto porque a veces "6 meses" realmente significa "no quiero lidiar con esto ahora" — y otras veces es algo real de tiempo donde debería tenerlo listo para empezar en el mes 4 y estar en vivo en el mes 6. ¿Me ayuda a entender?',
 'Got it. Let''s set a specific date — what works in [target month]?',
 'Entendido. Vamos a poner una fecha específica — ¿qué le funciona en [mes objetivo]?',
 NULL, NULL),

-- 10. "What about complex / Spanish / specialty calls?"
('what_about_complex_calls',
 'fit',
 'What about complex calls, Spanish-speaking customers, or situations Ana can''t handle?',
 '¿Qué pasa con llamadas complejas, clientes que hablan español, o situaciones que Ana no puede manejar?',
 'Great question — and the honest answer is: Ana handles way more than people expect, but she''s not magic.',
 'Excelente pregunta — y la respuesta honesta es: Ana maneja mucho más de lo que la gente espera, pero no es magia.',
 'Ana is fluent in Spanish — like, native-level fluent, not Google Translate fluent. She handles 80-85% of inbound calls completely on her own — booking, scheduling, answering common questions, qualifying leads. For the 15-20% that need a human — say, a billing dispute, a complex insurance question, or someone clearly upset — she does a warm transfer to your team and sends you the context up front. You never get a call cold. You get the customer + the summary of what they need + their Spanish or English preference. That''s actually better than what your receptionist does today.',
 'Ana habla español con fluidez — fluidez de nativa, no traducción de Google. Maneja 80-85% de las llamadas entrantes completamente sola — agendando, programando, contestando preguntas comunes, calificando prospectos. Para el 15-20% que necesita un humano — digamos, una disputa de facturación, una pregunta compleja de seguro, o alguien claramente molesto — hace una transferencia cálida a su equipo y le envía el contexto por adelantado. Nunca recibe una llamada en frío. Recibe al cliente + el resumen de lo que necesita + su preferencia de español o inglés. Eso de hecho es mejor que lo que su recepcionista hace hoy.',
 'Want me to walk you through exactly how she''d handle calls specific to your business on a 15-min demo?',
 '¿Quiere que le muestre exactamente cómo manejaría llamadas específicas de su negocio en una demostración de 15 minutos?',
 'Ricardo Diaz Insurance: 100% of Spanish-language calls handled natively, no transfers needed for routine questions.',
 'Ricardo Diaz Insurance: 100% de llamadas en español manejadas nativamente, sin transferencias para preguntas rutinarias.')

on conflict (code) do nothing;
