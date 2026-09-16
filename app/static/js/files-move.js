/** Dateien: Verschieben-Modal mit Ordnerbaum. */
(function () {
    'use strict';

    var moveState = {
        itemType: null,
        itemId: null,
        selected: null,
        modal: null,
        pathLabel: ''
    };
    var openGuard = 0;

    function moveLabels() {
        var modals = (window.FILES_I18N && window.FILES_I18N.modals && window.FILES_I18N.modals.move) || {};
        var actions = (window.FILES_I18N && window.FILES_I18N.actions) || {};
        return {
            title: modals.title || actions.move || 'Verschieben',
            loading: modals.loading || 'Lade Ziele…',
            confirm: modals.confirm || 'Hierher verschieben',
            empty: modals.empty || 'Keine Ordner verfügbar.',
            root_hint: modals.root_hint || 'Bereich (Root)',
            item_file: modals.item_file || 'Datei verschieben',
            item_folder: modals.item_folder || 'Ordner verschieben',
            selected: modals.selected || 'Ziel: {path}',
            expand: modals.expand || 'Aufklappen',
            collapse: modals.collapse || 'Zuklappen'
        };
    }

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .split('&').join('&amp;')
            .split('<').join('&lt;')
            .split('>').join('&gt;')
            .split('"').join('&quot;');
    }

    function setMoveError(message) {
        var el = document.getElementById('filesMoveError');
        if (!el) return;
        if (!message) {
            el.hidden = true;
            el.textContent = '';
            return;
        }
        el.hidden = false;
        el.textContent = message;
    }

    function setSelectedPath(pathLabel) {
        moveState.pathLabel = pathLabel || '';
        var el = document.getElementById('filesMoveSelectedPath');
        if (!el) return;
        if (!pathLabel) {
            el.hidden = true;
            el.textContent = '';
            return;
        }
        var tpl = moveLabels().selected || 'Ziel: {path}';
        el.textContent = tpl.split('{path}').join(pathLabel);
        el.hidden = false;
    }

    function setMoveSelection(payload, button, pathLabel) {
        moveState.selected = payload;
        document.querySelectorAll('.files-move-node.is-selected').forEach(function (el) {
            el.classList.remove('is-selected');
        });
        if (button) button.classList.add('is-selected');
        var confirmBtn = document.getElementById('filesMoveConfirmBtn');
        if (confirmBtn) confirmBtn.disabled = !payload;
        setSelectedPath(pathLabel || '');
    }

    function countFolders(nodes) {
        if (!nodes || !nodes.length) return 0;
        var n = nodes.length;
        nodes.forEach(function (node) {
            n += countFolders(node.children);
        });
        return n;
    }

    function renderFolderNodes(nodes, depth, spaceLabel) {
        if (!nodes || !nodes.length) return '';
        return nodes.map(function (node) {
            var hasChildren = !!(node.children && node.children.length);
            var kids = hasChildren
                ? '<div class="files-move-children" data-depth="' + (depth + 1) + '">' +
                    renderFolderNodes(node.children, depth + 1, spaceLabel) +
                  '</div>'
                : '';
            var toggle = hasChildren
                ? '<button type="button" class="files-move-toggle" aria-expanded="true" title="' +
                    escapeHtml(moveLabels().collapse) + '"><i class="bi bi-caret-down-fill" aria-hidden="true"></i></button>'
                : '<span class="files-move-toggle-spacer" aria-hidden="true"></span>';
            var colorStyle = node.color ? ' style="color:' + escapeHtml(node.color) + '"' : '';
            var path = spaceLabel + ' / ' + node.name;
            return (
                '<div class="files-move-branch" data-depth="' + depth + '">' +
                    '<div class="files-move-row" style="--files-move-depth:' + depth + '">' +
                        toggle +
                        '<button type="button" class="files-move-node" ' +
                            'data-folder-id="' + node.id + '" ' +
                            'data-path="' + escapeHtml(path) + '">' +
                            '<i class="bi bi-folder-fill folder-color-icon"' + colorStyle + '></i>' +
                            '<span class="text-truncate">' + escapeHtml(node.name) + '</span>' +
                        '</button>' +
                    '</div>' +
                    kids +
                '</div>'
            );
        }).join('');
    }

    function renderSpaces(spaces) {
        var labels = moveLabels();
        return (spaces || []).map(function (space) {
            var icon = space.view === 'ablage'
                ? 'bi-hdd'
                : (space.view === 'team' ? 'bi-people-fill' : 'bi-globe2');
            var colorDot = space.color
                ? '<span class="files-move-team-dot" style="background:' + escapeHtml(space.color) + '"></span>'
                : '<i class="bi ' + icon + '" aria-hidden="true"></i>';
            var teamAttr = space.team_id != null ? ' data-team-id="' + space.team_id + '"' : ' data-team-id=""';
            var folders = space.folders || [];
            var children = renderFolderNodes(folders, 1, space.label);
            var folderCount = countFolders(folders);
            var hasChildren = !!children;
            var spaceToggle = hasChildren
                ? '<button type="button" class="files-move-toggle" aria-expanded="true" title="' +
                    escapeHtml(labels.collapse) + '"><i class="bi bi-caret-down-fill" aria-hidden="true"></i></button>'
                : '<span class="files-move-toggle-spacer" aria-hidden="true"></span>';
            var countBadge = folderCount
                ? '<span class="files-move-count">' + folderCount + '</span>'
                : '';
            return (
                '<div class="files-move-space" data-space-key="' + escapeHtml(space.key) + '">' +
                    '<div class="files-move-row files-move-row--space" style="--files-move-depth:0">' +
                        spaceToggle +
                        '<button type="button" class="files-move-node files-move-space-root" ' +
                            'data-folder-id="" ' +
                            'data-view="' + escapeHtml(space.view) + '" ' +
                            'data-path="' + escapeHtml(space.label) + '"' +
                            teamAttr + '>' +
                            colorDot +
                            '<span class="text-truncate">' + escapeHtml(space.label) + '</span>' +
                            countBadge +
                            '<span class="files-move-root-hint">' + escapeHtml(labels.root_hint) + '</span>' +
                        '</button>' +
                    '</div>' +
                    (children ? '<div class="files-move-children files-move-children--space">' + children + '</div>' : '') +
                '</div>'
            );
        }).join('');
    }

    function toggleBranch(toggleBtn) {
        var row = toggleBtn.closest('.files-move-row');
        var branch = toggleBtn.closest('.files-move-branch, .files-move-space');
        if (!branch) return;
        var kids = null;
        if (row && row.parentElement === branch) {
            kids = branch.querySelector(':scope > .files-move-children');
        }
        if (!kids) return;
        var willOpen = kids.hidden;
        kids.hidden = !willOpen;
        toggleBtn.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
        toggleBtn.title = willOpen ? moveLabels().collapse : moveLabels().expand;
        var icon = toggleBtn.querySelector('i');
        if (icon) {
            icon.className = willOpen ? 'bi bi-caret-down-fill' : 'bi bi-caret-right-fill';
        }
    }

    function selectNode(btn) {
        var rawFolder = btn.getAttribute('data-folder-id');
        var view = btn.getAttribute('data-view') || '';
        var teamRaw = btn.getAttribute('data-team-id');
        var pathLabel = btn.getAttribute('data-path') || btn.textContent.trim();
        var targetFolderId = null;
        if (rawFolder !== '' && rawFolder != null) {
            targetFolderId = parseInt(rawFolder, 10);
        }
        var space = btn.closest('.files-move-space');
        var spaceRoot = space && space.querySelector('.files-move-space-root');
        var resolvedView = view || (spaceRoot && spaceRoot.getAttribute('data-view')) || window.FILES_VIEW || 'public';
        var resolvedTeam = teamRaw || (spaceRoot && spaceRoot.getAttribute('data-team-id')) || '';
        setMoveSelection({
            target_folder_id: Number.isFinite(targetFolderId) ? targetFolderId : null,
            view: resolvedView,
            team_id: resolvedTeam ? parseInt(resolvedTeam, 10) : undefined
        }, btn, pathLabel);
    }

    function bindTreeEvents(treeEl) {
        treeEl.onclick = function (e) {
            var toggle = e.target.closest('.files-move-toggle');
            if (toggle && treeEl.contains(toggle)) {
                e.preventDefault();
                e.stopPropagation();
                toggleBranch(toggle);
                return;
            }
            var node = e.target.closest('.files-move-node');
            if (node && treeEl.contains(node)) {
                e.preventDefault();
                e.stopPropagation();
                selectNode(node);
            }
        };
    }

    function loadDestinations() {
        var loading = document.getElementById('filesMoveLoading');
        var tree = document.getElementById('filesMoveTree');
        var confirmBtn = document.getElementById('filesMoveConfirmBtn');
        if (loading) loading.hidden = false;
        if (tree) {
            tree.hidden = true;
            tree.innerHTML = '';
        }
        if (confirmBtn) confirmBtn.disabled = true;
        setMoveError('');
        setSelectedPath('');
        moveState.selected = null;

        var params = new URLSearchParams();
        if (moveState.itemType === 'folder' && moveState.itemId) {
            params.set('exclude_folder_id', String(moveState.itemId));
        }
        var url = (window.FILES_MOVE_DESTINATIONS_URL || '/files/api/move-destinations') +
            (params.toString() ? ('?' + params.toString()) : '');

        fetch(url, { headers: { Accept: 'application/json' } })
            .then(function (response) {
                return response.json().catch(function () { return {}; }).then(function (data) {
                    return { response: response, data: data };
                });
            })
            .then(function (result) {
                if (loading) loading.hidden = true;
                if (!result.response.ok || !result.data.success) {
                    throw new Error(result.data.error || 'Laden fehlgeschlagen');
                }
                if (!tree) return;
                if (!result.data.spaces || !result.data.spaces.length) {
                    tree.innerHTML = '<div class="text-muted small p-2">' + escapeHtml(moveLabels().empty) + '</div>';
                } else {
                    tree.innerHTML = renderSpaces(result.data.spaces);
                    bindTreeEvents(tree);
                }
                tree.hidden = false;
            })
            .catch(function (err) {
                if (loading) loading.hidden = true;
                setMoveError(err.message || 'Laden fehlgeschlagen');
            });
    }

    function closeMenus() {
        try {
            document.querySelectorAll('.dropdown-menu.show').forEach(function (menu) {
                menu.classList.remove('show');
            });
            document.querySelectorAll('.dropdown.show').forEach(function (dropdown) {
                dropdown.classList.remove('show');
            });
            if (window.PrismateamsContextMenu && typeof window.PrismateamsContextMenu.close === 'function') {
                window.PrismateamsContextMenu.close();
            }
        } catch (err) { /* ignore */ }
    }

    function ensureModalOnBody(modalEl) {
        if (modalEl && modalEl.parentElement !== document.body) {
            document.body.appendChild(modalEl);
        }
        return modalEl;
    }

    window.openMoveModal = function openMoveModal(itemType, itemId, evt) {
        if (evt && typeof evt.preventDefault === 'function') {
            evt.preventDefault();
            evt.stopPropagation();
        }
        if (window.FILES_IS_TRASH) return false;

        var type = String(itemType || '').toLowerCase();
        var id = parseInt(itemId, 10);
        if ((type !== 'file' && type !== 'folder') || !Number.isFinite(id)) return false;

        var now = Date.now();
        if (now - openGuard < 400) return false;
        openGuard = now;

        closeMenus();

        moveState.itemType = type;
        moveState.itemId = id;

        var labels = moveLabels();
        var labelEl = document.getElementById('filesMoveItemLabel');
        if (labelEl) {
            labelEl.textContent = type === 'folder' ? labels.item_folder : labels.item_file;
        }

        var modalEl = ensureModalOnBody(document.getElementById('filesMoveModal'));
        if (!modalEl) {
            console.error('filesMoveModal fehlt im DOM');
            return false;
        }
        if (typeof bootstrap === 'undefined' || !bootstrap.Modal) {
            console.error('Bootstrap Modal nicht verfuegbar');
            return false;
        }

        window.setTimeout(function () {
            try {
                moveState.modal = bootstrap.Modal.getOrCreateInstance(modalEl);
                moveState.modal.show();
                loadDestinations();
            } catch (err) {
                console.error('openMoveModal failed', err);
            }
        }, 0);

        return false;
    };

    document.addEventListener('click', function (e) {
        if (e.target.closest('#filesMoveModal')) return;
        var trigger = e.target.closest('[data-files-move-type][data-files-move-id]');
        if (!trigger) return;
        e.preventDefault();
        e.stopPropagation();
        window.openMoveModal(
            trigger.getAttribute('data-files-move-type'),
            trigger.getAttribute('data-files-move-id'),
            e
        );
    }, true);

    function onReady() {
        ensureModalOnBody(document.getElementById('filesMoveModal'));
        var confirmBtn = document.getElementById('filesMoveConfirmBtn');
        if (!confirmBtn || confirmBtn.dataset.filesMoveBound === '1') return;
        confirmBtn.dataset.filesMoveBound = '1';
        confirmBtn.addEventListener('click', function () {
            if (!moveState.selected || !moveState.itemType || !moveState.itemId) return;
            confirmBtn.disabled = true;
            setMoveError('');
            fetch(window.FILES_MOVE_URL || '/files/move', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    item_type: moveState.itemType,
                    item_id: moveState.itemId,
                    target_folder_id: moveState.selected.target_folder_id,
                    view: moveState.selected.view,
                    team_id: moveState.selected.team_id
                })
            })
                .then(function (response) {
                    return response.json().catch(function () { return {}; }).then(function (data) {
                        return { response: response, data: data };
                    });
                })
                .then(function (result) {
                    if (!result.response.ok || !result.data.success) {
                        setMoveError(result.data.error || 'Verschieben fehlgeschlagen.');
                        confirmBtn.disabled = false;
                        return;
                    }
                    if (moveState.modal) moveState.modal.hide();
                    if (typeof window.showDnDMessage === 'function') {
                        var msg = (window.FILES_I18N && window.FILES_I18N.messages && window.FILES_I18N.messages.move_success) ||
                            'Element wurde verschoben.';
                        window.showDnDMessage(msg, 'success');
                    }
                    window.location.reload();
                })
                .catch(function () {
                    setMoveError('Verschieben fehlgeschlagen.');
                    confirmBtn.disabled = false;
                });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', onReady);
    } else {
        onReady();
    }
})();
