const im_elem = document.getElementById('derpi-img')
const id_elem = document.getElementById('derpi-id')
const desc_elem = document.getElementById('desc')
const error_e = document.getElementById('error-desc')
const submit_e = document.getElementById('submit-button')
const wc_elem = document.getElementById('word-count')
const ts_elem = document.getElementById('timestamp')
const id = +id_elem.innerHTML

async function showImage() {
	try {
  const res = await fetch(`https://derpibooru.org/api/v1/json/images/${id}`)
	const json = await res.json();
	const url = json.image.representations.medium;
	im_elem.onload = () => {
		desc.style.width = im_elem.width;
	}
	im_elem.src = url;
	console.log(url)
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
	const valid = (words < 77);
	submit_e.disabled = !valid;
}
desc_elem.addEventListener('input', checkWordLen)

ts_elem.value = (Date.now()/1000)|0;
