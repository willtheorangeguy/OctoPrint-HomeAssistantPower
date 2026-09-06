/*
 * Home Assistant Power - OctoPrint plugin frontend.
 */
$(function () {
    var PLUGIN_ID = "homeassistant_power";

    function HomeassistantPowerViewModel(parameters) {
        var self = this;

        self.settings = parameters[0];
        self.loginState = parameters[1];
        self.access = parameters[2];
        self.printerState = parameters[3];

        // --- live state -----------------------------------------------------

        self.states = ko.observable({});
        self.configured = ko.observableArray([]);
        self.printerEntity = ko.observable("");
        self.connectionError = ko.observable(null);
        self.autoOff = ko.observable({state: "idle"});
        self.energy = ko.observable({settings: {}, current_kwh: null, last: null});

        // --- settings editing ----------------------------------------------

        self.entities = ko.observableArray([]);
        self.controllableEntities = ko.observableArray([]);
        self.sensorEntities = ko.observableArray([]);
        self.testing = ko.observable(false);
        self.loadingEntities = ko.observable(false);
        self.testResult = ko.observable("");
        self.testOk = ko.observable(true);

        self.testResultClass = ko.pureComputed(function () {
            return self.testOk() ? "text-success" : "text-error";
        });

        self.canControl = ko.pureComputed(function () {
            return self.loginState.hasPermission(
                self.access.permissions.PLUGIN_HOMEASSISTANT_POWER_CONTROL
            );
        });

        // --- formatting -----------------------------------------------------

        function formatPower(watts) {
            if (watts === null || watts === undefined) return "—";
            if (Math.abs(watts) >= 1000) return (watts / 1000).toFixed(2) + " kW";
            return watts.toFixed(watts < 10 ? 1 : 0) + " W";
        }

        function energySettings() {
            return self.energy().settings || {};
        }

        function formatEnergy(kwh) {
            if (kwh === null || kwh === undefined) return "—";
            var text = kwh.toFixed(3) + " kWh";
            var cfg = energySettings();
            var price = parseFloat(cfg.cost_per_kwh);
            // Suppress a cost that rounds to zero -- "($0.00)" reads as a bug.
            if (!isNaN(price) && price > 0 && kwh * price >= 0.005) {
                text += " (" + (cfg.currency || "") + (kwh * price).toFixed(2) + ")";
            }
            return text;
        }

        function labelFor(entityId) {
            var match = _.find(self.configured(), function (entity) {
                return entity.entity_id === entityId;
            });
            return (match && match.label) || entityId || "the printer";
        }

        // --- navbar ---------------------------------------------------------

        self.navbarEntities = ko.pureComputed(function () {
            var states = self.states();
            var showPower = energySettings().show_in_navbar !== false;
            return _.filter(self.configured(), function (entity) {
                return entity.show_in_navbar !== false;
            }).map(function (entity) {
                var state = states[entity.entity_id] || {};
                return {
                    entity_id: entity.entity_id,
                    label: entity.label || entity.entity_id,
                    confirm_off: !!entity.confirm_off,
                    state: state.state || "unknown",
                    stateClass: "ha-power-state-" + (state.state || "unknown"),
                    showPower: showPower && state.power_w !== null && state.power_w !== undefined,
                    powerText: formatPower(state.power_w)
                };
            });
        });

        self.autoOffActive = ko.pureComputed(function () {
            var state = (self.autoOff() || {}).state;
            return state === "pending" || state === "cooldown" || state === "powering_off";
        });

        self.autoOffBadge = ko.pureComputed(function () {
            var info = self.autoOff() || {};
            if (info.state === "pending") return info.seconds_remaining + "s";
            if (info.state === "cooldown") return "↓";
            return "";
        });

        self.autoOffText = ko.pureComputed(function () {
            var info = self.autoOff() || {};
            if (info.state === "pending") {
                return "Powering off " + labelFor(info.entity_id) +
                    " in " + info.seconds_remaining + "s";
            }
            return info.detail || "";
        });

        // --- sidebar --------------------------------------------------------

        function printerState() {
            return self.states()[self.printerEntity()] || {};
        }

        self.printerPowerText = ko.pureComputed(function () {
            return formatPower(printerState().power_w);
        });

        self.energyTracking = ko.pureComputed(function () {
            return !!(self.energy() || {}).tracking;
        });

        self.currentPrintEnergyText = ko.pureComputed(function () {
            return formatEnergy((self.energy() || {}).current_kwh);
        });

        self.lastPrintEnergy = ko.pureComputed(function () {
            return (self.energy() || {}).last || null;
        });

        self.lastPrintEnergyText = ko.pureComputed(function () {
            var last = self.lastPrintEnergy();
            return last ? formatEnergy(last.kwh) : "—";
        });

        self.energyNotCumulative = ko.pureComputed(function () {
            var state = printerState();
            return state.energy_kwh !== null &&
                state.energy_kwh !== undefined &&
                state.cumulative === false;
        });

        self.sidebarVisible = ko.pureComputed(function () {
            var cfg = energySettings();
            if (cfg.enabled === false || cfg.show_sidebar === false) return false;
            var state = printerState();
            return state.power_w !== null && state.power_w !== undefined ||
                state.energy_kwh !== null && state.energy_kwh !== undefined;
        });

        // --- API ------------------------------------------------------------

        function command(name, payload) {
            return OctoPrint.simpleApiCommand(PLUGIN_ID, name, payload || {});
        }

        function applyPayload(payload) {
            if (!payload) return;
            if (payload.entities !== undefined) self.configured(payload.entities);
            if (payload.states !== undefined) self.states(payload.states);
            if (payload.printer_entity !== undefined) self.printerEntity(payload.printer_entity);
            if (payload.autooff !== undefined) self.autoOff(payload.autooff || {state: "idle"});
            if (payload.energy !== undefined) self.energy(payload.energy || {});
            if (payload.error !== undefined) self.connectionError(payload.error);
        }

        self.refresh = function () {
            OctoPrint.simpleApiGet(PLUGIN_ID).done(applyPayload);
        };

        function reportFailure(response) {
            var error = (response && response.error) || "Request failed";
            new PNotify({title: "Home Assistant Power", text: error, type: "error"});
        }

        self.turnOn = function (entity) {
            command("turn_on", {entity_id: entity.entity_id}).done(function (response) {
                if (response && response.ok === false) reportFailure(response);
            });
        };

        self.turnOff = function (entity) {
            var send = function (force) {
                command("turn_off", {entity_id: entity.entity_id, force: !!force})
                    .done(function (response) {
                        if (response && response.ok === false) {
                            if (response.needs_confirmation) {
                                showConfirmationDialog({
                                    message: "A print is running. Cutting power to " +
                                        entity.label + " will abort it. Continue?",
                                    onproceed: function () { send(true); }
                                });
                            } else {
                                reportFailure(response);
                            }
                        }
                    });
            };

            if (entity.confirm_off && entity.state === "on") {
                showConfirmationDialog({
                    message: "Turn off " + entity.label + "?",
                    onproceed: function () { send(false); }
                });
            } else {
                send(false);
            }
        };

        self.cancelAutoOff = function () {
            command("cancel_auto_off");
        };

        self.powerOnPrinter = function () {
            command("power_on_printer").done(function (response) {
                if (response && response.ok === false) reportFailure(response);
            });
        };

        // --- settings -------------------------------------------------------

        // Resolved once the settings viewmodel has its data, and referenced
        // directly by the settings template. Reaching through
        // `settings.settings.plugins.<id>` in every binding is unreadable and
        // easy to get wrong.
        self.pluginSettings = null;

        self.onBeforeBinding = function () {
            self.pluginSettings = self.settings.settings.plugins[PLUGIN_ID];
            // Populate the editable rows before binding so the printer-entity
            // dropdown has its options on the first pass.
            self.loadEntityRows();
        };

        function pluginSettings() {
            return self.pluginSettings || self.settings.settings.plugins[PLUGIN_ID];
        }

        function makeRow(source) {
            source = source || {};
            return {
                entity_id: ko.observable(source.entity_id || ""),
                label: ko.observable(source.label || ""),
                show_in_navbar: ko.observable(source.show_in_navbar !== false),
                confirm_off: ko.observable(!!source.confirm_off),
                power_sensor: ko.observable(source.power_sensor || ""),
                energy_sensor: ko.observable(source.energy_sensor || "")
            };
        }

        self.configuredEntityIds = ko.pureComputed(function () {
            return self.entities()
                .map(function (row) { return row.entity_id(); })
                .filter(function (id) { return !!id; });
        });

        self.addEntity = function () {
            self.entities.push(makeRow());
        };

        self.removeEntity = function (row) {
            self.entities.remove(row);
        };

        self.detectSensors = function (row) {
            var entityId = row.entity_id();
            if (!entityId) return;
            command("detect_sensors", {entity_id: entityId}).done(function (response) {
                if (!response || response.ok === false) {
                    reportFailure(response);
                    return;
                }
                if (response.power_sensor) row.power_sensor(response.power_sensor);
                if (response.energy_sensor) row.energy_sensor(response.energy_sensor);
                if (!response.power_sensor && !response.energy_sensor) {
                    new PNotify({
                        title: "Home Assistant Power",
                        text: "No matching power or energy sensors found for " +
                            entityId + ". Enter them manually if the plug has any.",
                        type: "info"
                    });
                }
            });
        };

        self.testConnection = function () {
            self.testing(true);
            self.testResult("Testing…");
            self.testOk(true);
            command("test_connection", {
                base_url: pluginSettings().base_url(),
                access_token: pluginSettings().access_token(),
                verify_certificate: pluginSettings().verify_certificate()
            }).done(function (response) {
                self.testOk(!!(response && response.ok));
                self.testResult(
                    response && response.ok
                        ? "Connected to Home Assistant."
                        : (response && response.error) || "Connection failed."
                );
            }).fail(function () {
                self.testOk(false);
                self.testResult("Connection failed.");
            }).always(function () {
                self.testing(false);
            });
        };

        self.loadEntities = function () {
            self.loadingEntities(true);
            command("list_entities").done(function (response) {
                if (!response || response.ok === false) {
                    reportFailure(response);
                    return;
                }
                self.controllableEntities(response.controllable || []);
                self.sensorEntities(response.sensors || []);
            }).always(function () {
                self.loadingEntities(false);
            });
        };

        self.loadEntityRows = function () {
            var stored = ko.toJS(pluginSettings().entities) || [];
            self.entities(stored.map(makeRow));
        };

        self.onSettingsShown = function () {
            self.loadEntityRows();
            self.testResult("");
        };

        self.onSettingsBeforeSave = function () {
            var rows = self.entities()
                .map(function (row) {
                    return {
                        entity_id: (row.entity_id() || "").trim(),
                        label: (row.label() || "").trim(),
                        show_in_navbar: row.show_in_navbar(),
                        confirm_off: row.confirm_off(),
                        power_sensor: (row.power_sensor() || "").trim(),
                        energy_sensor: (row.energy_sensor() || "").trim()
                    };
                })
                .filter(function (row) {
                    return row.entity_id.indexOf(".") > 0;
                });
            pluginSettings().entities(rows);
        };

        // --- notifications --------------------------------------------------

        var autoOffNotification = null;

        function closeAutoOffNotification() {
            if (autoOffNotification) {
                autoOffNotification.remove();
                autoOffNotification = null;
            }
        }

        function updateAutoOffNotification(info) {
            var active = info.state === "pending" || info.state === "cooldown";
            if (!active) {
                closeAutoOffNotification();
                return;
            }

            var text = info.state === "pending"
                ? "Powering off " + labelFor(info.entity_id) +
                  " in " + info.seconds_remaining + "s."
                : (info.detail || "Waiting for the printer to cool down.");

            if (autoOffNotification) {
                autoOffNotification.update({text: text});
                return;
            }

            autoOffNotification = new PNotify({
                title: "Powering off after the print",
                text: text,
                type: "info",
                hide: false,
                confirm: {
                    confirm: true,
                    buttons: [{
                        text: "Keep power on",
                        addClass: "btn-primary",
                        click: function () {
                            self.cancelAutoOff();
                            closeAutoOffNotification();
                        }
                    }]
                },
                buttons: {closer: false, sticker: false}
            });
        }

        // --- plumbing -------------------------------------------------------

        self.onDataUpdaterPluginMessage = function (plugin, message) {
            if (plugin !== PLUGIN_ID || !message) return;

            if (message.type === "states") {
                // The push carries the same shape as the GET, so no follow-up
                // request is needed.
                applyPayload(message);
            } else if (message.type === "autooff") {
                self.autoOff(message);
                updateAutoOffNotification(message);
            } else if (message.type === "print_energy") {
                var record = message.record || {};
                new PNotify({
                    title: "Print energy",
                    text: "This print used " + formatEnergy(record.kwh) + ".",
                    type: "info"
                });
            } else if (message.type === "poweron") {
                if (message.state === "failed") {
                    reportFailure({error: message.error});
                } else if (message.state === "timeout") {
                    new PNotify({
                        title: "Home Assistant Power",
                        text: "The plug was switched on but the printer did not " +
                            "connect in time. Connect manually once it has booted.",
                        type: "notice"
                    });
                }
            }
        };

        self.onAfterBinding = function () {
            self.refresh();

            // The sidebar panel only makes sense once a sensor is configured,
            // so toggle its wrapper rather than showing an empty box.
            var wrapper = $("#sidebar_plugin_" + PLUGIN_ID + "_wrapper");
            ko.computed(function () {
                wrapper.toggle(self.sidebarVisible());
            });
        };

        self.onUserPermissionsChanged = self.onUserLoggedIn = self.onUserLoggedOut = function () {
            self.refresh();
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: HomeassistantPowerViewModel,
        dependencies: [
            "settingsViewModel",
            "loginStateViewModel",
            "accessViewModel",
            "printerStateViewModel"
        ],
        elements: [
            "#navbar_plugin_homeassistant_power",
            "#sidebar_plugin_homeassistant_power",
            "#settings_plugin_homeassistant_power"
        ]
    });
});
