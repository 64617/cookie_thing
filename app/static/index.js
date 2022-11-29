const _libs = {
  JSZip: 'https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js',
	//FileSaver: 'https://cdnjs.cloudflare.com/ajax/libs/FileSaver.js/2.0.5/FileSaver.min.js'
	FileSaver: '/static/FileSaver.js'
}
async function use(name) {
	if (typeof _libs[name] === "string")
		_libs[name] = await import(_libs[name])
	return _libs[name]
}

function tempSpinner(needsSpinner, promise) {
	const spinner = document.createElement('div')
	spinner.className = 'spinner'
	spinner.id = 'temp-spinner'
	old_inner = needsSpinner.innerHTML;
	needsSpinner.innerHTML = "";
	needsSpinner.appendChild(spinner);
	needsSpinner.disabled = true;
	return promise.finally(res => {
		needsSpinner.removeChild(spinner);
		needsSpinner.innerHTML = old_inner;
		needsSpinner.disabled = false;
		return res;
	})
}

function sanitizeTagList(s) {
	return s
		.replace(/\s+/g,' ') // remove extra whitespaces
		.replace(/^\s+|\s+$/,'') 
		.replace(/^,|,$/g,'')  // extra: remove trailing/starting commas
		.replaceAll(', ', ',');
}

const im_elem = document.getElementById('derpi-img')
const id_elem = document.getElementById('derpi-id')
const desc_elem = document.getElementById('desc')
const error_e = document.getElementById('error-desc')
const submit_e = document.getElementById('submit-button')
const wc_elem = document.getElementById('word-count')
const ts_elem = document.getElementById('timestamp')
const tags_e = document.getElementById('tag-dump')
const filter_e = document.getElementById('image-filter')
const custom_filter_e = document.getElementById('filter-menu')
const custom_filter_button_e = document.getElementById('filter-menu-button')
const custom_filter_toggle_e = document.getElementById('filter-menu-toggle')
const superlist_e = document.getElementById('superlist')
const whitelist_e = document.getElementById('whitelist')
const blacklist_e = document.getElementById('blacklist')
const export_button_e = document.getElementById('button-export-personal')
const export_include_images_e = document.getElementById('export-include-images')
const export_use_filter_e = document.getElementById('export-use-filter')
const export_min_len_e = document.getElementById('export-min-len')
const id = +id_elem.innerHTML
let char_set;

function setCookie(name,value,days) {
    var expires = "";
    if (days) {
        var date = new Date();
        date.setTime(date.getTime() + (days*24*60*60*1000));
        expires = "; expires=" + date.toUTCString();
    }
    document.cookie = name + "=" + (value || "")  + expires + "; path=/";
}
function getCookie(name, otherwise=null) {
    var nameEQ = name + "=";
    var ca = document.cookie.split(';');
    for(var i=0;i < ca.length;i++) {
        var c = ca[i];
        while (c.charAt(0)==' ') c = c.substring(1,c.length);
        if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length,c.length);
    }
    return otherwise;
}
function eraseCookie(name) {   
    document.cookie = name +'=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT;';
}

if (getCookie('image_filter') === null) {
	setCookie('image_filter', 'SAFE', 99)
}
const image_filter = getCookie('image_filter')
const FILTER_LIST = ["SAFE", "any", "NSFW", "NSFL", "PONY", "custom"]
const filter_idx = FILTER_LIST.indexOf(image_filter)
filter_e.options[filter_idx].selected = true;

custom_filter_toggle_e.onclick = () => {
	const opening = custom_filter_e.hidden;
	custom_filter_e.hidden = !opening;
	custom_filter_toggle_e.innerHTML = opening ? '▼' : '▶'
}
function loadCustomFilter(hide=true) {
	custom_filter_toggle_e.style.visibility = 'visible'
	superlist_e.value = getCookie('superlist','').replace(',', ', ')
	whitelist_e.value = getCookie('whitelist','').replace(',', ', ')
	blacklist_e.value = getCookie('blacklist','').replace(',', ', ')
	if (!hide) {
		custom_filter_e.hidden = false;
		custom_filter_toggle_e.innerHTML = '▼'
	}
}
if (image_filter === "custom") {
	loadCustomFilter()
}
filter_e.onchange = e => {
	if (e.currentTarget.value === 'custom') {
		loadCustomFilter(hide=false)
	} else {
		setCookie('image_filter', e.currentTarget.value);
		window.location.reload();
	}
}
custom_filter_button_e.onclick = () => {
	const [slist,wlist,blist] = [superlist_e.value, whitelist_e.value, blacklist_e.value]
	setCookie('superlist', sanitizeTagList(slist))
	setCookie('whitelist', sanitizeTagList(wlist))
	setCookie('blacklist', sanitizeTagList(blist))
	setCookie('image_filter', 'custom');
	window.location.reload();
}
function customTagListValidator() {
	const to_submit = sanitizeTagList(this.value)
	if (to_submit !== '') {
		for (const w of to_submit.split(',')) {
			if (!/^[0-9 a-z:-]+$/.test(w)) {
				this.style.boxShadow = "0 0 4px 1px red"
				custom_filter_button_e.disabled = true;
				return
			}
		}
	}
	this.style.boxShadow = "inherit"
	custom_filter_button_e.disabled = false;
}
superlist_e.addEventListener('input', customTagListValidator)
whitelist_e.addEventListener('input', customTagListValidator)
blacklist_e.addEventListener('input', customTagListValidator)

function appendtext(s) {
	desc_elem.value += s+' ';
	checkWordLen()
}
function addtag(s) {
	if (char_set.has(s)) {
		s = s.split(' ')
			.map(w => w[0].toUpperCase() + w.substr(1))
			.join(" ");
	}
	const linked_tag = document.createElement('a')
	linked_tag.href = '#'
	linked_tag.innerHTML = s;
	linked_tag.onclick = e => {
		e.preventDefault()
		appendtext(s)
	}
	tags_e.appendChild(linked_tag)
	linked_tag.insertAdjacentHTML('afterend', ' ')
}
async function get_characters() {
	if (localStorage.getItem('char_list') === null) {
		const res = await fetch('/static/character_tags.txt');
		const txt = await res.text();
		localStorage.setItem('char_list', txt.trim());
	}
	return localStorage.getItem('char_list').split('\n')
}
async function derpi_image_info(id) {
  const res = await fetch(`https://derpibooru.org/api/v1/json/images/${id}`)
	return await res.json();
}
async function showImage() {
	try {
	char_set = new Set(await get_characters())
	const json = await derpi_image_info(id);
	const url = json.image.representations.medium;
	im_elem.onload = () => {
		tags_e.style.maxWidth = desc.style.width = im_elem.width;
	}
	im_elem.src = url;
	json.image.tags.forEach(s => addtag(s))
	} catch (e) {
		console.log(e)
		error_e.innerHTML = 'Error (refresh the page):'+e;
		error_e.hidden = false
	}
}
//showImage();

function checkWordLen() {
	const s = desc_elem.value.trim()
	const words = s ? s.split(' ').length : 0; // just approx
	wc_elem.innerHTML = words;
	const warning = (words > 49);
	const too_much = (words > 99);
	if (too_much) {
		desc_elem.style.boxShadow = "0 0 4px 1px red"
	} else if (warning) {
		desc_elem.style.boxShadow = "0 0 4px 1px orange"
	} else {
		desc_elem.style.boxShadow = "inherit"
	}
	submit_e.disabled = too_much;
}
desc_elem.addEventListener('input', checkWordLen)

ts_elem.value = (Date.now()/1000)|0;

async function get_captions(use_filter) {
	const res = await fetch(`/api/collect/${+use_filter}`, {
		credentials: 'include'
	})
	const json = await res.json();
	return json
}
async function derpi_image_dl(id) {
	const json = await derpi_image_info(id);
	const full_url = json.image.representations.full;
	const res = await fetch(full_url);
	return [await res.blob(), full_url.split('/').pop()];
}
function validate_prompt(p_text, min_words) {
	// Make sure prompts aren't too long
	if (p_text.length > 250) {
		console.log("PRUNING:", p_text);
		// look for the last '.' within limit.
		let i;
		for (i = 250; i > 0; i--) {
			if (p_text[i] === '.') break;
		}
    p_text = p_text.slice(0,i);
	}
	return p_text.split(' ').length < min_words ?
		'' : p_text;
}

async function add_images_to_zip(captions) {
	await use("JSZip"); // cursed
	const zip = JSZip(); // no new because ????
	for (const [id,p_text] of captions) {
		const [im, fname] = await derpi_image_dl(id);
		const ext = fname.split('.').pop();
		zip.file(`${p_text}.${ext}`, im);
	}
	return zip;
}
async function export_captions(grab_images, use_filter, min_words) {
	await use("FileSaver"); // cursed
	const captions = (await get_captions(use_filter))
		.map(([id,p_text]) => [id,validate_prompt(p_text,min_words)])
		.filter(t => t[1]);

	if (grab_images) {
		const zip = await add_images_to_zip(captions);
		const outfile = await zip.generateAsync({type: 'blob'});
		saveAs(outfile, 'mycaptions.zip');
	}
	const outfile = new Blob(
		[JSON.stringify(captions)],
	  {'type': 'application/json'}
	);
	return saveAs(outfile, 'mycaptions.json');
}
export_button_e.addEventListener('click', () => {
	export_button_e.value = 'downloading...'
	const p = export_captions(
		export_include_images_e.checked,
		export_use_filter_e.checked,
		+export_min_len_e.value,
	);
	tempSpinner(export_button_e, p)
		.then(() => export_button_e.value = 'done!')
})

// modal
function model_content(title, body_id) {
	const modal_body = document.getElementById(body_id);
	modal_body.hidden = false;
	document.body.removeChild(modal_body);
	//
	const content = document.createElement('div');
	content.className = "modal-content"
	//
	const header = document.createElement('div');
	header.className = "modal-header"
	const h5 = document.createElement('h5');
	h5.className = "modal-title";
	h5.innerHTML = title;
	header.appendChild(h5);
	//
	const body = document.createElement('div');
	body.className = "modal-body";
	body.appendChild(modal_body);
	//
	const footer = document.createElement('div');
	footer.className = "modal-footer"
	const button = document.createElement('button');
	button.id = "close"
	button.className = "ml-auto btn btn-secondary";
	button.innerHTML = 'Close'
	button.onclick = () => modal_disable(body_id);
	footer.appendChild(button);
	//
	content.appendChild(header);
	content.appendChild(body);
	content.appendChild(footer);
	return content;
}
function modal_enable(title, body_id) {
	const root = document.createElement('div')
	root.id = 'modal-root'
	root.tabIndex = -1
	root.style = "position: relative; z-index: 1050; display: block;"
	//
	const first = document.createElement('div');
	first.className = "modal fade show";
	first.style = "display: block;";
	first.onclick = () => modal_disable(body_id);
	first.setAttribute('role', 'dialog');
	first.role = "dialog";
	first.tabIndex = -1;
	//
	const inner = document.createElement('div');
	inner.onclick = e => e.stopPropagation();
	inner.id = "modal";
	inner.setAttribute('role', 'document');
	inner.className = "modal-dialog";
	//inner.style = "display: block;"
	//inner.tabIndex = -1;
	inner.appendChild(model_content(title, body_id));
	//
	first.appendChild(inner);
	const second = document.createElement('div');
	second.className = "modal-backdrop fade show"
	//
	const preroot = document.createElement('div')
	preroot.className = "";
	preroot.appendChild(first);
	preroot.appendChild(second);
	root.append(preroot)
	//
	document.body.appendChild(root);
}
function modal_disable(body_id) {
	const modal_body = document.getElementById(body_id);
	modal_body.hidden = true;
	const root = document.getElementById('modal-root')
	document.body.removeChild(root);
	document.body.appendChild(modal_body);
}

const export_link_e = document.getElementById('open-export');
export_link_e.addEventListener('click', () => {
	modal_enable('Export captions', 'modal-body-export')
});


