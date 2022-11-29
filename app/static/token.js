import Tokenizer from "https://deno.land/x/clip_bpe@v0.0.6/mod.js";
let t = new Tokenizer();

const error_e = document.getElementById('error-desc')
const desc_textarea_e = document.getElementById('desc')
const token_output_e = document.getElementById('token-output')
const token_count_e = document.getElementById('token-count')

function tokenize(s) {
  const ids = t.encode(s);
  const text = ids.map(
    tk => '['+t.decoder[tk].replace('</w>','')+']'
  ).join(" ");
  return [ids.length,text]
}
function update() {
  const p_text = desc_textarea_e.value
  const [len, res] = tokenize(p_text)
  token_count_e.innerText = len
  token_output_e.innerText = res
}
function show_error(e) {
  error_e.innerText = e
  console.error(e);
}

desc_textarea_e.addEventListener('input', () => {
  try {
    update();
  } catch (e) {
    show_error(e);
  }
})

desc_textarea_e.disabled = false
token_output_e.innerText = ''
desc_textarea_e.focus()
