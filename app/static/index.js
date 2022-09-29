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
async function showImage() {
	try {
	char_set = new Set(await get_characters())
  const res = await fetch(`https://derpibooru.org/api/v1/json/images/${id}`)
	const json = await res.json();
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
showImage();

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
