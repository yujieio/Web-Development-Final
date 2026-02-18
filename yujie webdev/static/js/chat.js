let chats = JSON.parse(localStorage.getItem("chats")) || {};

let lastMessageTime =
  JSON.parse(localStorage.getItem("lastMessageTime")) || {};

let blockedChats = JSON.parse(localStorage.getItem("blockedChats")) || {};

function saveBlockedChats() {
  localStorage.setItem("blockedChats", JSON.stringify(blockedChats));
}


showEmptyState();

let currentChat = null;
const fakeUsers = [
  { name: "Alex Tan", avatar: "A" },
  { name: "Bella Lim", avatar: "B" },
  { name: "Chris Ng", avatar: "C" },
  { name: "Dylan Chua", avatar: "D" },
  { name: "Emma Lee", avatar: "E" },
  { name: "Fiona Goh", avatar: "F" },
  { name: "Raghav Kumar", avatar: "R" },
  { name: "Zane Ooi", avatar: "Z" },
  { name: "Grace Koh", avatar: "G" },
  { name: "Henry Teo", avatar: "H" },
  { name: "Iris Wong", avatar: "I" },
  { name: "Jake Chen", avatar: "J" },
  { name: "Karen Sim", avatar: "K" },
  { name: "Liam Toh", avatar: "L" },
  { name: "Maya Patel", avatar: "M" },
  { name: "Noah Singh", avatar: "N" },
  { name: "Olivia Ong", avatar: "O" },
  { name: "Priya Kumar", avatar: "P" },
];

const fakeReplies = [
  "helloooo",
  "wassup?",
  "sup bro",
  "heyyy",
  "hii",
  "sup",
  "hey man",
  "whats good",
  "👋",
];

const avatarColors = [
  "#4CAF50", 
  "#2196F3", 
  "#9C27B0", 
  "#FF9800", 
  "#E91E63", 
  "#009688", 
  "#3F51B5", 
  "#795548", 
  "#607D8B"  
];

function getAvatarColor(name) {
  if (!avatarColorMap[name]) {
    const randomColor =
      avatarColors[Math.floor(Math.random() * avatarColors.length)];
    avatarColorMap[name] = randomColor;
    localStorage.setItem("avatarColors", JSON.stringify(avatarColorMap));
  }
  return avatarColorMap[name];
}
 
let avatarColorMap =
  JSON.parse(localStorage.getItem("avatarColors")) || {};


function saveChats() {
  localStorage.setItem("chats", JSON.stringify(chats));
}


function openChat(element, name) {
  currentChat = name;

  if (!lastMessageTime[name]) {
    lastMessageTime[name] = Date.now();
  }

  hideEmptyState();
hideTyping();

  document.getElementById("chatName").innerText = name;
  const color = getAvatarColor(name);

const headerAvatar = document.getElementById("headerAvatar");
headerAvatar.innerText = name[0].toUpperCase();
headerAvatar.style.backgroundColor = color;

const profileAvatar = document.getElementById("profileAvatar");
profileAvatar.innerText = name[0].toUpperCase();
profileAvatar.style.backgroundColor = color;


  document.querySelectorAll(".chat-item").forEach(item =>
    item.classList.remove("active")
  );

  if (element) element.classList.add("active");

  updateInputState();
  renderMessages();
  updateBlockButton();
  updateBlockedLabel();
}





function sendMessage() {
  if (blockedChats[currentChat]) {
    alert("You cannot send messages to a blocked contact.");
    return;
  }

  const input = document.getElementById("messageInput");
  const text = input.value.trim();
  if (!text) return;

  chats[currentChat].push({
    sender: "me",
    text,
    time: Date.now()
  });

  saveChats();
  saveLastMessageTime();
  input.value = "";

  updateChatPreview(currentChat, text);
  renderMessages();

  const replyChat = currentChat;

  showTyping(replyChat);

  setTimeout(() => {
    if (currentChat !== replyChat) return;

    const reply = getRandomReply();

    chats[replyChat].push({
      sender: "them",
      text: reply,
      time: Date.now()
    });

    saveChats();
    saveLastMessageTime();

    hideTyping();
    updateChatPreview(replyChat, reply);
    renderMessages();
  }, 1200 + Math.random() * 1000);
}


function handleEnter(event) {
  if (event.key === "Enter") {
    sendMessage();
  }
}


function renderMessages() {
  if (!currentChat || !chats[currentChat]) return;

  const box = document.getElementById("messages");
  box.innerHTML = "";

  chats[currentChat].forEach(msg => {
    const div = document.createElement("div");
    div.className =
      msg.sender === "me" ? "my-message" : "their-message";
    div.innerText = msg.text;
    box.appendChild(div);
  });

  box.scrollTop = box.scrollHeight;
}


function getRandomReply() {
  return fakeReplies[Math.floor(Math.random() * fakeReplies.length)];
}

function showTyping(name) {
  const indicator = document.getElementById("typingIndicator");
  indicator.querySelector(".typing-name").innerText = `${name} is typing`;
  indicator.classList.remove("hidden");

  const messages = document.getElementById("messages");
  messages.scrollTop = messages.scrollHeight;
}



function hideTyping() {
  document.getElementById("typingIndicator").classList.add("hidden");
}

function openAddFriendModal() {
  document.getElementById("friendSearchInput").value = "";
  renderFriendResults();

  const modal = new bootstrap.Modal(
    document.getElementById("addFriendModal")
  );
  modal.show();
}

function renderFriendResults() {
  const input = document
    .getElementById("friendSearchInput")
    .value.toLowerCase();

  const container = document.getElementById("friendResults");
  container.innerHTML = "";

  fakeUsers
    .filter(user =>
      user.name.toLowerCase().includes(input)
    )
    .forEach(user => {
      const alreadyAdded = chats[user.name];

      const row = document.createElement("div");
      row.className =
        "d-flex justify-content-between align-items-center mb-2";

   row.innerHTML = `
  <div class="d-flex align-items-center gap-2">
    <div
      class="chat-avatar"
      style="background:${getAvatarColor(user.name)}"
    >
      ${user.avatar}
    </div>
    <span class="friend-name">${user.name}</span>
  </div>
  <button class="btn btn-sm ${
    alreadyAdded ? "btn-secondary" : "btn-success"
  }" ${alreadyAdded ? "disabled" : ""}>
    ${alreadyAdded ? "Added" : "Add"}
  </button>
`;


      if (!alreadyAdded) {
        row.querySelector("button").onclick = () =>
          addFriendFromSearch(user);
      }

      container.appendChild(row);
    });
}

function addFriendFromSearch(user) {
  chats[user.name] = [];
  lastMessageTime[user.name] = 0;
  saveChats();
  saveLastMessageTime();

  loadChatsFromStorage();

  bootstrap.Modal
    .getInstance(document.getElementById("addFriendModal"))
    .hide();
}


function toggleProfile() {
  let profile = document.getElementById("profilePanel");
  profile.classList.toggle("hidden");
}

function searchContacts() {
  const input = document.getElementById("searchInput");
  const filter = input.value.toLowerCase();
  const chatItems = document.querySelectorAll(".chat-item");

  chatItems.forEach(item => {
    const text = item.textContent.toLowerCase();
    item.style.display = text.includes(filter) ? "block" : "none";
  });
}

function updateChatPreview(chatName, lastMessage) {
  lastMessageTime[chatName] = Date.now();
  saveLastMessageTime();

  const chatItems = document.querySelectorAll(".chat-item");

  chatItems.forEach(item => {
    const name = item.querySelector("strong").innerText;
    if (name === chatName) {
      item.querySelector("p").innerText = truncate(lastMessage, 35);
    }
  });

  sortChats();
}

function sortChats() {
  const sidebar = document.querySelector(".sidebar");
  const chatItems = Array.from(sidebar.querySelectorAll(".chat-item"));
  const addFriendBtn = sidebar.querySelector(".add-friend-btn");

  chatItems.sort((a, b) => {
    const nameA = a.querySelector("strong").innerText;
    const nameB = b.querySelector("strong").innerText;

    return (lastMessageTime[nameB] || 0) - (lastMessageTime[nameA] || 0);
  });

  // Insert chats in correct order
  let insertAfter = addFriendBtn;

  chatItems.forEach(item => {
    sidebar.insertBefore(item, insertAfter.nextSibling);
    insertAfter = item; // 👈 advance anchor
  });
}



function showEmptyState() {
  document.getElementById("emptyState").style.display = "flex";
  document.getElementById("messages").style.display = "none";
  document.getElementById("chatHeader").style.display = "none";
  document.getElementById("inputArea").style.display = "none";
}

function hideEmptyState() {
  document.getElementById("emptyState").style.display = "none";
  document.getElementById("messages").style.display = "block";
  document.getElementById("chatHeader").style.display = "block";
  document.getElementById("inputArea").style.display = "flex";
}



//finding friends :>

function addFriend() {
  let name = prompt("Enter friend's name:");
  lastMessageTime[name] = 0;

  if (!name) return;
  name = name.trim();

  if (name === "") return;

  if (chats[name]) {
    alert("This chat already exists.");
    return;
  }

  chats[name] = [];
  saveChats();


  const sidebar = document.querySelector(".sidebar");

  const chatItem = document.createElement("div");
  chatItem.className = "chat-item";
  chatItem.onclick = function () {
    openChat(chatItem, name);
  };

const avatar = document.createElement("div");
avatar.className = "chat-avatar";
avatar.innerText = name[0].toUpperCase();
avatar.style.backgroundColor = getAvatarColor(name);


  const textWrap = document.createElement("div");
  textWrap.className = "chat-text";

  const strong = document.createElement("strong");
  strong.innerText = name;

  const preview = document.createElement("p");
  preview.innerText = "";


  textWrap.appendChild(strong);
textWrap.appendChild(preview);

chatItem.appendChild(avatar);
chatItem.appendChild(textWrap);



  const addFriendBtn = document.querySelector(".add-friend-btn");
  sidebar.insertBefore(chatItem, addFriendBtn.nextSibling);

  openChat(chatItem, name);
}



function truncate(text, max = 40) {
  return text.length > max ? text.slice(0, max) + "…" : text;
}



//ze danger buttons

function deleteChat() {
  showModal(
    "Delete chat",
    `Delete chat with ${currentChat}? This cannot be undone.`,
    "Delete",
    () => {
      delete chats[currentChat];
      saveChats();


      document.querySelectorAll(".chat-item").forEach(item => {
        if (item.querySelector("strong").innerText === currentChat) {
          item.remove();
        }
      });

      currentChat = null;
       document.getElementById("profilePanel").classList.add("hidden"); 

      if (Object.keys(chats).length) {
        const firstItem = document.querySelector(".chat-item");
        openChat(firstItem, firstItem.querySelector("strong").innerText);
      } else {
        showEmptyState();
      }
    }
  );
}




function blockChat() {
  const isBlocked = blockedChats[currentChat];

  showModal(
    isBlocked ? "Unblock user" : "Block user",
    isBlocked
      ? `Unblock ${currentChat}?`
      : `Block ${currentChat}? You won't be able to send messages.`,
    isBlocked ? "Unblock" : "Block",
    () => {
      blockedChats[currentChat] = !isBlocked;
      saveBlockedChats();
      updateInputState();
      updateBlockButton();
      updateBlockedLabel();
    }
  );
}


function updateBlockButton() {
  const blockBtn = document.querySelector(
    '.profile button[onclick="blockChat()"]'
  );

  if (blockedChats[currentChat]) {
    blockBtn.innerText = "Unblock";
    blockBtn.style.background = "#555";
  } else {
    blockBtn.innerText = "Block";
    blockBtn.style.background = "red";
  }
}

function updateBlockedLabel() {
  const label = document.getElementById("blockedLabel");

  if (blockedChats[currentChat]) {
    label.classList.remove("hidden");
  } else {
    label.classList.add("hidden");
  }
}


function reportChat() {
  showModal(
    "Report user",
    `Report ${currentChat} for inappropriate behavior?`,
    "Report",
    () => {}
  );
}


function updateInputState() {
  const input = document.getElementById("messageInput");
  input.disabled = blockedChats[currentChat] === true;
}


let modalAction = null;

function showModal(title, body, confirmText, actionFn) {
  document.getElementById("modalTitle").innerText = title;
  document.getElementById("modalBody").innerText = body;

  const confirmBtn = document.getElementById("modalConfirmBtn");
  confirmBtn.innerText = confirmText;

  modalAction = actionFn;

  const modal = new bootstrap.Modal(
    document.getElementById("actionModal")
  );
  modal.show();
}

document
  .getElementById("modalConfirmBtn")
  .addEventListener("click", () => {
    if (modalAction) modalAction();
    bootstrap.Modal.getInstance(
      document.getElementById("actionModal")
    ).hide();
  });

window.addEventListener("storage", (event) => {
  if (event.key === "chats") {
    chats = JSON.parse(event.newValue) || {};
    renderMessages();
  }
});

function saveLastMessageTime() {
  localStorage.setItem(
    "lastMessageTime",
    JSON.stringify(lastMessageTime)
  );
}


function loadChatsFromStorage() {
  const sidebar = document.querySelector(".sidebar");
  const addFriendBtn = sidebar.querySelector(".add-friend-btn");

  sidebar.querySelectorAll(".chat-item").forEach(item => item.remove());

  const sortedNames = Object.keys(chats).sort((a, b) => {
    return (lastMessageTime[b] || 0) - (lastMessageTime[a] || 0);
  });

  sortedNames.forEach(name => {
    const chatItem = document.createElement("div");
    chatItem.className = "chat-item";
    chatItem.onclick = () => openChat(chatItem, name);

   const avatar = document.createElement("div");
avatar.className = "chat-avatar";
avatar.innerText = name[0].toUpperCase();
avatar.style.backgroundColor = getAvatarColor(name);


    const textWrap = document.createElement("div");
    textWrap.className = "chat-text";

    const strong = document.createElement("strong");
    strong.innerText = name;

    const preview = document.createElement("p");
    const lastMsg = chats[name]?.slice(-1)[0]?.text || "";
    preview.innerText = truncate(lastMsg, 35);

    textWrap.append(strong, preview);
    chatItem.append(avatar, textWrap);

    sidebar.insertBefore(chatItem, addFriendBtn.nextSibling);
  });

  if (!sortedNames.length) showEmptyState();
}


loadChatsFromStorage();
sortChats();